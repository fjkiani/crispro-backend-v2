from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import httpx
import os
import statistics
import sys
from pathlib import Path

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

CBIO_BASE = "https://www.cbioportal.org/api"

def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.getenv("CBIO_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _safe_json(resp: httpx.Response):
    try:
        if resp is None:
            return None
        text = resp.text or ""
        if not text.strip():
            return None
        return resp.json()
    except Exception:
        return None

def _pybioportal_path() -> str:
    # ../oncology-backend/tests/pyBioPortal-master/pybioportal relative to this file
    here = Path(__file__).resolve()
    root = here.parents[4]  # .../crispr-assistant-main
    target = root / "oncology-coPilot" / "oncology-backend" / "tests" / "pyBioPortal-master" / "pybioportal"
    return str(target)

def _fallback_mm_via_pybioportal(study: str, genes: List[str], limit: int) -> List[Dict[str, Any]]:
    try:
        p = _pybioportal_path()
        if p not in sys.path:
            sys.path.append(p)
        # Lazy imports
        from pybioportal import molecular_profiles as mp  # type: ignore
        from pybioportal import sample_lists as sl  # type: ignore
        from pybioportal import mutations as mut  # type: ignore
        import pandas as pd  # type: ignore

        df_prof = mp.get_all_molecular_profiles_in_study(study)
        profile_id = None
        if isinstance(df_prof, pd.DataFrame) and "molecularProfileId" in df_prof.columns:
            cand = df_prof["molecularProfileId"].astype(str).tolist()
            for pid in cand:
                if pid.endswith("_mutations"):
                    profile_id = pid
                    break
            if profile_id is None and cand:
                for pid in cand:
                    if "MUTATION" in str(pid).upper():
                        profile_id = pid
                        break
        if not profile_id:
            return []

        df_lists = sl.get_all_sample_lists_in_study(study)
        sample_list_id = None
        if isinstance(df_lists, pd.DataFrame) and "sampleListId" in df_lists.columns:
            c2 = df_lists["sampleListId"].astype(str).tolist()
            for sid in c2:
                if sid.endswith("_all"):
                    sample_list_id = sid
                    break
            if sample_list_id is None and c2:
                sample_list_id = c2[0]

        df_muts = mut.get_muts_in_mol_prof_by_sample_list_id(profile_id, sample_list_id, projection="DETAILED", pageSize=max(5000, limit))
        if not isinstance(df_muts, pd.DataFrame) or df_muts.empty:
            return []
        # Normalize columns
        def col(name: str) -> str:
            for c in df_muts.columns:
                if c.lower() == name.lower():
                    return c
            return name
        out: List[Dict[str, Any]] = []
        genes_set = {g.upper() for g in (genes or []) if g}
        for _, row in df_muts.iterrows():
            gene_sym = str(row.get(col("gene_hugoGeneSymbol")) or row.get(col("hugoGeneSymbol")) or "").upper()
            if genes_set and gene_sym not in genes_set:
                continue
            try:
                out.append({
                    "disease": "multiple myeloma",
                    "gene": gene_sym,
                    "hgvs_p": str(row.get(col("proteinChange")) or ""),
                    "chrom": str(row.get(col("chromosome")) or ""),
                    "pos": int(row.get(col("startPosition")) or 0) if row.get(col("startPosition")) else "",
                    "ref": str(row.get(col("referenceAllele")) or "").upper(),
                    "alt": str(row.get(col("variantAllele")) or "").upper(),
                    "build": "GRCh38",
                    "exposure_pi": 0,
                    "exposure_imid": 0,
                    "exposure_anti_cd38": 0,
                    "sample_id": str(row.get(col("sampleId")) or ""),
                })
            except Exception:
                continue
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []

def _fallback_mm_multi(studies: List[str], genes: List[str], limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    for sid in studies:
        batch = _fallback_mm_via_pybioportal(sid, genes, max(0, limit - len(rows)))
        for r in batch:
            key = (r.get("sample_id"), r.get("gene"), r.get("hgvs_p"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)
            if len(rows) >= limit:
                return rows
    return rows

def _http_choose_profile_sync(study_id: str) -> str:
    try:
        with httpx.Client(timeout=30, headers=_headers()) as client:
            r = client.get(f"{CBIO_BASE}/studies/{study_id}/molecular-profiles")
            if r.status_code >= 400:
                return ""
            profiles = _safe_json(r) or []
            for p in profiles:
                pid = p.get("molecularProfileId") or ""
                if pid.endswith("_mutations"):
                    return pid
            for p in profiles:
                if (p.get("molecularAlterationType") or "").upper().startswith("MUTATION"):
                    return p.get("molecularProfileId") or ""
            return ""
    except Exception:
        return ""

def _http_choose_sample_list_sync(study_id: str) -> str:
    try:
        with httpx.Client(timeout=30, headers=_headers()) as client:
            r = client.get(f"{CBIO_BASE}/studies/{study_id}/sample-lists")
            if r.status_code >= 400:
                return ""
            lists = _safe_json(r) or []
            # Prefer sequenced set for mutation profiles if available
            for it in lists:
                sid = (it.get("sampleListId") or "")
                if "sequenced" in sid:
                    return sid
            for it in lists:
                sid = (it.get("sampleListId") or "")
                if sid.endswith("_all"):
                    return sid
            return (lists[0].get("sampleListId") if lists else "")
    except Exception:
        return ""

def _fallback_mm_http_paged(studies: List[str], genes: List[str], limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    genes_param = ",".join(genes) if genes else None
    for study in studies:
        profile_id = _http_choose_profile_sync(study)
        if not profile_id:
            continue
        sample_list_id = _http_choose_sample_list_sync(study)
        page = 0
        while len(rows) < limit:
            try:
                with httpx.Client(timeout=60, headers=_headers()) as client:
                    params: Dict[str, Any] = {
                        "projection": "DETAILED",
                        "pageSize": 1000,
                        "pageNumber": page,
                    }
                    if sample_list_id:
                        params["sampleListId"] = sample_list_id
                    if genes_param:
                        params["hugoGeneSymbols"] = genes_param
                    r = client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=params)
                    if r.status_code >= 400:
                        break
                    data = _safe_json(r) or []
                    if not data:
                        break
                    for m in data:
                        gene_obj = m.get("gene") or {}
                        gene = (gene_obj.get("hugoGeneSymbol") or "").upper()
                        key = (m.get("sampleId"), gene, m.get("proteinChange"))
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append({
                            "disease": "multiple myeloma",
                            "gene": gene,
                            "hgvs_p": m.get("proteinChange") or "",
                            "chrom": str(m.get("chromosome") or ""),
                            "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                            "ref": str(m.get("referenceAllele") or "").upper(),
                            "alt": str(m.get("variantAllele") or "").upper(),
                            "build": "GRCh38",
                            "exposure_pi": 0,
                            "exposure_imid": 0,
                            "exposure_anti_cd38": 0,
                            "sample_id": m.get("sampleId") or "",
                        })
                        if len(rows) >= limit:
                            return rows
                    page += 1
            except Exception:
                break
    return rows

def _fallback_hrd_http_paged(study: str, genes: List[str], limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen = set()
    profile_id = _http_choose_profile_sync(study)
    if not profile_id:
        return rows
    sample_list_id = _http_choose_sample_list_sync(study)
    page = 0
    genes_param = ",".join(genes) if genes else None
    while len(rows) < limit:
        try:
            with httpx.Client(timeout=60, headers=_headers()) as client:
                params: Dict[str, Any] = {
                    "projection": "DETAILED",
                    "pageSize": 1000,
                    "pageNumber": page,
                }
                if sample_list_id:
                    params["sampleListId"] = sample_list_id
                if genes_param:
                    params["hugoGeneSymbols"] = genes_param
                r = client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=params)
                if r.status_code >= 400:
                    break
                data = _safe_json(r) or []
                if not data:
                    break
                for m in data:
                    gene_obj = m.get("gene") or {}
                    gene = (gene_obj.get("hugoGeneSymbol") or "").upper()
                    key = (m.get("sampleId"), gene, m.get("proteinChange"))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({
                        "disease": "ovarian cancer",
                        "gene": gene,
                        "hgvs_p": m.get("proteinChange") or "",
                        "chrom": str(m.get("chromosome") or ""),
                        "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                        "ref": str(m.get("referenceAllele") or "").upper(),
                        "alt": str(m.get("variantAllele") or "").upper(),
                        "build": "GRCh38",
                        "outcome_platinum": 0,
                        "sample_id": m.get("sampleId") or "",
                    })
                    if len(rows) >= limit:
                        return rows
                page += 1
        except Exception:
            break
    return rows

async def _get_mutation_profile_id(client: httpx.AsyncClient, study_id: str) -> str:
    """Resolve the correct mutation molecular profile id for a study.
    Prefer ids ending with '_mutations' or alterationType == 'MUTATION_EXTENDED'.
    """
    r = await client.get(f"{CBIO_BASE}/studies/{study_id}/molecular-profiles")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=f"failed to list molecular profiles for study {study_id}: {r.text}")
    profiles = _safe_json(r) or []
    # Prefer *_mutations
    for p in profiles:
        pid = p.get("molecularProfileId") or ""
        if pid.endswith("_mutations"):
            return pid
    # Fallback: alteration type
    for p in profiles:
        if (p.get("molecularAlterationType") or "").upper().startswith("MUTATION"):
            pid = p.get("molecularProfileId")
            if pid:
                return pid
    raise HTTPException(status_code=404, detail=f"no mutation molecular profile found for study {study_id}")

async def _get_sample_list_id(client: httpx.AsyncClient, study_id: str) -> str:
    """Resolve an appropriate sample list id for a study, prefer *_sequenced for mutations."""
    r = await client.get(f"{CBIO_BASE}/studies/{study_id}/sample-lists")
    if r.status_code >= 400:
        # Not fatal; some queries can work without a sample list
        return ""
    lists = _safe_json(r) or []
    # Prefer sequenced set for mutation profiles if available
    for it in lists:
        sid = it.get("sampleListId") or ""
        if "sequenced" in sid:
            return sid
    for it in lists:
        sid = it.get("sampleListId") or ""
        if sid.endswith("_all"):
            return sid
    return lists[0].get("sampleListId") if lists else ""

@router.post("/extract_hrd_cohort")
async def extract_hrd_cohort(request: Dict[str, Any]):
    try:
        study = (request or {}).get("study_id", "ov_tcga")
        genes = (request or {}).get("genes", ["BRCA1","BRCA2"])
        limit = int((request or {}).get("limit", 200))
        # Use POST /fetch endpoint with entrezGeneIds for proper filtering
        async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
            profile_id = await _get_mutation_profile_id(client, study)
            sample_list_id = await _get_sample_list_id(client, study)
            
            # Map gene symbols to entrez IDs
            gene_map = {"BRCA1": 672, "BRCA2": 675, "TP53": 7157, "PTEN": 5728, "ATM": 472, "PALB2": 79728}
            entrez_ids = [gene_map.get(g.upper()) for g in genes if g.upper() in gene_map] if genes else []
            
            # Build payload - projection goes in query params, not body
            payload = {}
            if sample_list_id:
                payload["sampleListId"] = sample_list_id
            if entrez_ids:
                payload["entrezGeneIds"] = entrez_ids
            
            rmut = await client.post(
                f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations/fetch",
                params={"projection": "DETAILED"},
                json=payload
            )
            if rmut.status_code >= 400:
                raise HTTPException(status_code=rmut.status_code, detail=f"mutations fetch failed: {rmut.text[:200]}")
            
            rmut_json = _safe_json(rmut)
            muts = rmut_json if isinstance(rmut_json, list) else (rmut_json or {}).get("items", [])
            if not muts:
                raise HTTPException(status_code=500, detail=f"No mutations returned from API")
            # Get unique patient IDs from sample IDs (TCGA-XX-XXXX from TCGA-XX-XXXX-01)
            patient_ids = list({m.get("patientId") for m in muts if m.get("patientId")})[:1000]
            
            # Fetch patient-level clinical data for outcomes
            patient_data: Dict[str, Dict[str, Any]] = {}
            chunk = 200
            for i in range(0, len(patient_ids), chunk):
                try:
                    # Fetch patient-level attributes for DFS/OS outcomes
                    for pid in patient_ids[i:i+chunk]:
                        try:
                            rpt = await client.get(f"{CBIO_BASE}/studies/{study}/patients/{pid}/clinical-data", params={"projection": "SUMMARY"})
                            if rpt.status_code < 400:
                                pt_json = _safe_json(rpt) or []
                                pt_dict = {item.get("clinicalAttributeId"): item.get("value") for item in pt_json}
                                patient_data[pid] = pt_dict
                        except Exception:
                            continue
                except Exception:
                    continue
            # Build cohort rows
            out: List[Dict[str, Any]] = []
            genes_filter = set([g.upper() for g in genes if g]) if genes else None
            for m in muts[:limit]:
                sid = m.get("sampleId")
                pid = m.get("patientId")
                gene = ((m.get("gene") or {}).get("hugoGeneSymbol") or "").upper()
                if genes_filter and gene not in genes_filter:
                    continue
                
                # Get patient-level outcomes
                pt_data = patient_data.get(pid, {})
                dfs_status = pt_data.get("DFS_STATUS", "")
                os_status = pt_data.get("OS_STATUS", "")
                dfs_months = pt_data.get("DFS_MONTHS", "")
                
                # Label based on DFS (disease-free survival) status:
                # 1 = recurred/progressed (poor outcome)
                # 0 = no recurrence or missing (censored/good outcome)
                outcome_poor = 1 if any([
                    "recurred" in dfs_status.lower(),
                    "progressed" in dfs_status.lower(),
                ]) else 0
                
                out.append({
                    "disease": "ovarian cancer",
                    "gene": gene,
                    "hgvs_p": m.get("proteinChange") or "",
                    "chrom": str(m.get("chr") or ""),  # cBioPortal uses "chr" not "chromosome"
                    "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else 0,
                    "ref": str(m.get("referenceAllele") or "").upper(),
                    "alt": str(m.get("variantAllele") or "").upper(),
                    "build": "GRCh38",
                    "outcome_platinum": outcome_poor,  # Now using DFS status (1=recurred, 0=censored/no recurrence)
                    "dfs_status": dfs_status,
                    "dfs_months": dfs_months,
                    "os_status": os_status,
                    "sample_id": sid,
                    "patient_id": pid,
                })
            return {"rows": out, "count": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_hrd_cohort failed: {e}")


@router.post("/extract_mm_cohort")
async def extract_mm_cohort(request: Dict[str, Any]):
    """Extract a Multiple Myeloma cohort from cBioPortal for a set of genes.
    Input: { study_id: string, genes: [str], limit?: int }
    Output: { rows: [...], count }
    """
    try:
        study = (request or {}).get("study_id", "mm_broad")
        genes = (request or {}).get("genes", ["KRAS","NRAS","BRAF","TP53"])  # common MM drivers
        limit = int((request or {}).get("limit", 300))
        params = {
            "projection": "DETAILED",
            "pageSize": limit,
        }
        if genes:
            params["hugoGeneSymbols"] = [g for g in genes if g]  # Filter empty strings
        # Allow multi-study fallback via study_ids
        study_ids = (request or {}).get("study_ids") or []
        if isinstance(study_ids, str):
            study_ids = [s.strip() for s in study_ids.split(",") if s.strip()]
        if not study_ids:
            study_ids = [study, "mmrf_commpass_ia14", "myeloma_msk_2018"]
        async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
            profile_id = await _get_mutation_profile_id(client, study)
            sample_list_id = await _get_sample_list_id(client, study)
            qparams = dict(params)
            if sample_list_id:
                qparams["sampleListId"] = sample_list_id
            rmut = await client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=qparams)
            if rmut.status_code >= 400:
                # REST failed; try multi-study fallback
                fb_rows = _fallback_mm_multi(study_ids, genes, limit)
                if fb_rows:
                    return {"rows": fb_rows, "count": len(fb_rows), "provenance": {"method": "pybioportal_fallback_v1", "studies": study_ids}}
                raise HTTPException(status_code=rmut.status_code, detail=f"mutations fetch failed: {rmut.text}")
            rmut_json = _safe_json(rmut)
            muts = rmut_json if isinstance(rmut_json, list) else (rmut_json or {}).get("items", [])
            if not muts:
                fb_rows = _fallback_mm_multi(study_ids, genes, limit)
                if fb_rows:
                    return {"rows": fb_rows, "count": len(fb_rows), "provenance": {"method": "pybioportal_fallback_v1", "studies": study_ids}}
            sample_ids = list({m.get("sampleId") for m in muts if m.get("sampleId")})[:1000]
            # Clinical drug exposure (chunked) – look for PI/IMiD/anti-CD38 keywords
            rows_by_sample: Dict[str, Dict[str, Any]] = {}
            chunk = 200
            for i in range(0, len(sample_ids), chunk):
                payload = {
                    "entityIds": sample_ids[i:i+chunk],
                    "entityType": "SAMPLE",
                    "projection": "DETAILED",
                    "attributeIds": [
                        "DRUG_NAME","TREATMENT_TYPE","THERAPY_NAME","CLINICAL_TREATMENT_TYPE"
                    ],
                }
                rclin = await client.post(f"{CBIO_BASE}/clinical-data/fetch", json=payload)
                if rclin.status_code < 400:
                    clin_json = _safe_json(rclin) or []
                    for row in clin_json:
                        sid = row.get("entityId")
                        if sid:
                            rows_by_sample.setdefault(sid, {}).update(row)
            # Build rows
            out: List[Dict[str, Any]] = []
            genes_filter = set([g.upper() for g in genes if g]) if genes else None
            for m in muts[:limit]:
                sid = m.get("sampleId")
                gene = ((m.get("gene") or {}).get("hugoGeneSymbol") or "").upper()
                if genes_filter and gene not in genes_filter:
                    continue
                clin = rows_by_sample.get(sid, {})
                txt = str(clin).lower()
                exposure_pi = 1 if any(k in txt for k in ["bortezomib","carfilzomib","ixazomib","proteasome"]) else 0
                exposure_imid = 1 if any(k in txt for k in ["lenalidomide","thalidomide","pomalidomide","imid"]) else 0
                exposure_cd38 = 1 if any(k in txt for k in ["daratumumab","isatuximab","anti-cd38"]) else 0
                out.append({
                    "disease": "multiple myeloma",
                    "gene": gene,
                    "hgvs_p": m.get("proteinChange") or "",
                    "chrom": str(m.get("chromosome") or ""),
                    "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                    "ref": str(m.get("referenceAllele") or "").upper(),
                    "alt": str(m.get("variantAllele") or "").upper(),
                    "build": "GRCh38",
                    "exposure_pi": exposure_pi,
                    "exposure_imid": exposure_imid,
                    "exposure_anti_cd38": exposure_cd38,
                    "sample_id": sid,
                })
            return {"rows": out, "count": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_mm_cohort failed: {e}")

@router.post("/extract_and_benchmark")
async def extract_and_benchmark(request: Dict[str, Any]):
    """Unified endpoint: extract cohort and (optionally) run a minimal benchmark.
    Input: { mode: 'extract_only'|'run_only'|'both', study_id, genes[], limit?, profile? }
    Output: { rows?, count?, metrics?, profile }
    """
    try:
        mode = (request or {}).get("mode", "both").lower()
        profile = (request or {}).get("profile", "baseline")
        disease = (request or {}).get("disease", "ovarian cancer").lower()
        rows: List[Dict[str, Any]] = []
        # 1) Extract if needed
        if mode in ("both", "extract_only"):
            if disease == "multiple myeloma":
                res = await extract_mm_cohort(request)
            else:
                res = await extract_hrd_cohort(request)
            rows = (res or {}).get("rows") or []
        elif mode == "run_only":
            # Expect rows provided inline
            rows = (request or {}).get("rows") or []
        # 2) Minimal benchmark (proxy): compute prevalence and a dummy AUPRC proxy
        metrics: Dict[str, Any] = {}
        if mode in ("both", "run_only"):
            n = len(rows)
            by_gene: Dict[str, Dict[str, Any]] = {}
            if disease == "multiple myeloma":
                # Compute prevalence of each exposure class
                pi_pos = sum(1 for r in rows if int(r.get("exposure_pi") or 0) == 1)
                imid_pos = sum(1 for r in rows if int(r.get("exposure_imid") or 0) == 1)
                cd38_pos = sum(1 for r in rows if int(r.get("exposure_anti_cd38") or 0) == 1)
                for r in rows:
                    g = (r.get("gene") or "").upper()
                    by_gene.setdefault(g, {"n": 0})
                    by_gene[g]["n"] += 1
                gene_stats = [
                    {"gene": g, "n": v["n"]}
                    for g, v in by_gene.items()
                ]
                metrics = {
                    "count": n,
                    "exposure_pi_prevalence": round((pi_pos / n) if n else 0.0, 3),
                    "exposure_imid_prevalence": round((imid_pos / n) if n else 0.0, 3),
                    "exposure_anti_cd38_prevalence": round((cd38_pos / n) if n else 0.0, 3),
                    "by_gene": gene_stats,
                    "profile": profile,
                }
            else:
                positives = sum(1 for r in rows if int(r.get("outcome_platinum") or 0) == 1)
                prevalence = (positives / n) if n else 0.0
                auprc_proxy = round(0.5 * (0.1 + prevalence), 3)
                for r in rows:
                    g = (r.get("gene") or "").upper()
                    by_gene.setdefault(g, {"n": 0, "pos": 0})
                    by_gene[g]["n"] += 1
                    if int(r.get("outcome_platinum") or 0) == 1:
                        by_gene[g]["pos"] += 1
                gene_stats = [
                    {
                        "gene": g,
                        "n": v["n"],
                        "prevalence": round((v["pos"] / v["n"]) if v["n"] else 0.0, 3),
                    }
                    for g, v in by_gene.items()
                ]
                metrics = {
                    "count": n,
                    "positives": positives,
                    "prevalence": round(prevalence, 3),
                    "auprc_proxy": auprc_proxy,
                    "by_gene": gene_stats,
                    "profile": profile,
                }
        return {
            "rows": rows if mode in ("both", "extract_only") else None,
            "count": len(rows) if mode in ("both", "extract_only") else None,
            "metrics": metrics if metrics else None,
            "profile": profile,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_and_benchmark failed: {e}")



from typing import Dict, Any, List
import httpx
import os

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

CBIO_BASE = "https://www.cbioportal.org/api"

def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.getenv("CBIO_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

@router.post("/extract_hrd_cohort")
async def extract_hrd_cohort(request: Dict[str, Any]):
    try:
        study = (request or {}).get("study_id", "ov_tcga")
        genes = (request or {}).get("genes", ["BRCA1","BRCA2"])
        limit = int((request or {}).get("limit", 200))
        # Mutations for BRCA1/2
        profile_id = f"{study}_mutations"
        sample_list_id = f"{study}_all"
        params = {
            "sampleListId": sample_list_id,
            "hugoGeneSymbols": genes,
            "projection": "DETAILED",
            "pageSize": limit,
        }
        async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
            rmut = await client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=params)
            if rmut.status_code >= 400:
                raise HTTPException(status_code=rmut.status_code, detail=f"mutations fetch failed: {rmut.text}")
            muts = rmut.json() if isinstance(rmut.json(), list) else rmut.json().get("items", [])
            sample_ids = list({m.get("sampleId") for m in muts if m.get("sampleId")})[:1000]
            # Clinical drug exposure (chunked)
            rows: Dict[str, Dict[str, Any]] = {}
            chunk = 200
            for i in range(0, len(sample_ids), chunk):
                payload = {
                    "entityIds": sample_ids[i:i+chunk],
                    "entityType": "SAMPLE",
                    "projection": "DETAILED",
                    "attributeIds": ["DRUG_NAME","TREATMENT_TYPE","THERAPY_NAME","CLINICAL_TREATMENT_TYPE"],
                }
                rclin = await client.post(f"{CBIO_BASE}/clinical-data/fetch", json=payload)
                if rclin.status_code < 400:
                    for row in (rclin.json() or []):
                        sid = row.get("entityId")
                        if sid:
                            rows.setdefault(sid, {}).update(row)
            # Build cohort rows
            out: List[Dict[str, Any]] = []
            for m in muts[:limit]:
                sid = m.get("sampleId")
                gene = ((m.get("gene") or {}).get("hugoGeneSymbol") or "").upper()
                if gene not in set([g.upper() for g in genes]):
                    continue
                clin = rows.get(sid, {})
                txt = str(clin).lower()
                exposed = 1 if any(k in txt for k in ["carboplatin","cisplatin","oxaliplatin","platinum"]) else 0
                out.append({
                    "disease": "ovarian cancer",
                    "gene": gene,
                    "hgvs_p": m.get("proteinChange") or "",
                    "chrom": str(m.get("chromosome") or ""),
                    "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                    "ref": str(m.get("referenceAllele") or "").upper(),
                    "alt": str(m.get("variantAllele") or "").upper(),
                    "build": "GRCh38",
                    "outcome_platinum": exposed,
                    "sample_id": sid,
                })
            return {"rows": out, "count": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_hrd_cohort failed: {e}")



        profile_id = f"{study}_mutations"
        sample_list_id = f"{study}_all"
        params = {
            "sampleListId": sample_list_id,
            "hugoGeneSymbols": genes,
            "projection": "DETAILED",
            "pageSize": limit,
        }
        async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
            rmut = await client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=params)
            if rmut.status_code >= 400:
                raise HTTPException(status_code=rmut.status_code, detail=f"mutations fetch failed: {rmut.text}")
            muts = rmut.json() if isinstance(rmut.json(), list) else rmut.json().get("items", [])
            sample_ids = list({m.get("sampleId") for m in muts if m.get("sampleId")})[:1000]
            # Clinical drug exposure (chunked)
            rows: Dict[str, Dict[str, Any]] = {}
            chunk = 200
            for i in range(0, len(sample_ids), chunk):
                payload = {
                    "entityIds": sample_ids[i:i+chunk],
                    "entityType": "SAMPLE",
                    "projection": "DETAILED",
                    "attributeIds": ["DRUG_NAME","TREATMENT_TYPE","THERAPY_NAME","CLINICAL_TREATMENT_TYPE"],
                }
                rclin = await client.post(f"{CBIO_BASE}/clinical-data/fetch", json=payload)
                if rclin.status_code < 400:
                    for row in (rclin.json() or []):
                        sid = row.get("entityId")
                        if sid:
                            rows.setdefault(sid, {}).update(row)
            # Build cohort rows
            out: List[Dict[str, Any]] = []
            for m in muts[:limit]:
                sid = m.get("sampleId")
                gene = ((m.get("gene") or {}).get("hugoGeneSymbol") or "").upper()
                if gene not in set([g.upper() for g in genes]):
                    continue
                clin = rows.get(sid, {})
                txt = str(clin).lower()
                exposed = 1 if any(k in txt for k in ["carboplatin","cisplatin","oxaliplatin","platinum"]) else 0
                out.append({
                    "disease": "ovarian cancer",
                    "gene": gene,
                    "hgvs_p": m.get("proteinChange") or "",
                    "chrom": str(m.get("chromosome") or ""),
                    "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                    "ref": str(m.get("referenceAllele") or "").upper(),
                    "alt": str(m.get("variantAllele") or "").upper(),
                    "build": "GRCh38",
                    "outcome_platinum": exposed,
                    "sample_id": sid,
                })
            return {"rows": out, "count": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_hrd_cohort failed: {e}")




from typing import Dict, Any, List
import httpx
import os

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

CBIO_BASE = "https://www.cbioportal.org/api"

def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.getenv("CBIO_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

@router.post("/extract_hrd_cohort")
async def extract_hrd_cohort(request: Dict[str, Any]):
    try:
        study = (request or {}).get("study_id", "ov_tcga")
        genes = (request or {}).get("genes", ["BRCA1","BRCA2"])
        limit = int((request or {}).get("limit", 200))
        # Mutations for BRCA1/2
        profile_id = f"{study}_mutations"
        sample_list_id = f"{study}_all"
        params = {
            "sampleListId": sample_list_id,
            "hugoGeneSymbols": genes,
            "projection": "DETAILED",
            "pageSize": limit,
        }
        async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
            rmut = await client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=params)
            if rmut.status_code >= 400:
                raise HTTPException(status_code=rmut.status_code, detail=f"mutations fetch failed: {rmut.text}")
            muts = rmut.json() if isinstance(rmut.json(), list) else rmut.json().get("items", [])
            sample_ids = list({m.get("sampleId") for m in muts if m.get("sampleId")})[:1000]
            # Clinical drug exposure (chunked)
            rows: Dict[str, Dict[str, Any]] = {}
            chunk = 200
            for i in range(0, len(sample_ids), chunk):
                payload = {
                    "entityIds": sample_ids[i:i+chunk],
                    "entityType": "SAMPLE",
                    "projection": "DETAILED",
                    "attributeIds": ["DRUG_NAME","TREATMENT_TYPE","THERAPY_NAME","CLINICAL_TREATMENT_TYPE"],
                }
                rclin = await client.post(f"{CBIO_BASE}/clinical-data/fetch", json=payload)
                if rclin.status_code < 400:
                    for row in (rclin.json() or []):
                        sid = row.get("entityId")
                        if sid:
                            rows.setdefault(sid, {}).update(row)
            # Build cohort rows
            out: List[Dict[str, Any]] = []
            for m in muts[:limit]:
                sid = m.get("sampleId")
                gene = ((m.get("gene") or {}).get("hugoGeneSymbol") or "").upper()
                if gene not in set([g.upper() for g in genes]):
                    continue
                clin = rows.get(sid, {})
                txt = str(clin).lower()
                exposed = 1 if any(k in txt for k in ["carboplatin","cisplatin","oxaliplatin","platinum"]) else 0
                out.append({
                    "disease": "ovarian cancer",
                    "gene": gene,
                    "hgvs_p": m.get("proteinChange") or "",
                    "chrom": str(m.get("chromosome") or ""),
                    "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                    "ref": str(m.get("referenceAllele") or "").upper(),
                    "alt": str(m.get("variantAllele") or "").upper(),
                    "build": "GRCh38",
                    "outcome_platinum": exposed,
                    "sample_id": sid,
                })
            return {"rows": out, "count": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_hrd_cohort failed: {e}")



        profile_id = f"{study}_mutations"
        sample_list_id = f"{study}_all"
        params = {
            "sampleListId": sample_list_id,
            "hugoGeneSymbols": genes,
            "projection": "DETAILED",
            "pageSize": limit,
        }
        async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
            rmut = await client.get(f"{CBIO_BASE}/molecular-profiles/{profile_id}/mutations", params=params)
            if rmut.status_code >= 400:
                raise HTTPException(status_code=rmut.status_code, detail=f"mutations fetch failed: {rmut.text}")
            muts = rmut.json() if isinstance(rmut.json(), list) else rmut.json().get("items", [])
            sample_ids = list({m.get("sampleId") for m in muts if m.get("sampleId")})[:1000]
            # Clinical drug exposure (chunked)
            rows: Dict[str, Dict[str, Any]] = {}
            chunk = 200
            for i in range(0, len(sample_ids), chunk):
                payload = {
                    "entityIds": sample_ids[i:i+chunk],
                    "entityType": "SAMPLE",
                    "projection": "DETAILED",
                    "attributeIds": ["DRUG_NAME","TREATMENT_TYPE","THERAPY_NAME","CLINICAL_TREATMENT_TYPE"],
                }
                rclin = await client.post(f"{CBIO_BASE}/clinical-data/fetch", json=payload)
                if rclin.status_code < 400:
                    for row in (rclin.json() or []):
                        sid = row.get("entityId")
                        if sid:
                            rows.setdefault(sid, {}).update(row)
            # Build cohort rows
            out: List[Dict[str, Any]] = []
            for m in muts[:limit]:
                sid = m.get("sampleId")
                gene = ((m.get("gene") or {}).get("hugoGeneSymbol") or "").upper()
                if gene not in set([g.upper() for g in genes]):
                    continue
                clin = rows.get(sid, {})
                txt = str(clin).lower()
                exposed = 1 if any(k in txt for k in ["carboplatin","cisplatin","oxaliplatin","platinum"]) else 0
                out.append({
                    "disease": "ovarian cancer",
                    "gene": gene,
                    "hgvs_p": m.get("proteinChange") or "",
                    "chrom": str(m.get("chromosome") or ""),
                    "pos": int(m.get("startPosition") or 0) if m.get("startPosition") else "",
                    "ref": str(m.get("referenceAllele") or "").upper(),
                    "alt": str(m.get("variantAllele") or "").upper(),
                    "build": "GRCh38",
                    "outcome_platinum": exposed,
                    "sample_id": sid,
                })
            return {"rows": out, "count": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract_hrd_cohort failed: {e}")



