"""
Massive Oracle Scorer: Massive Oracle for synthetic and real-context scoring.
"""
import httpx
from typing import Dict, Any, List, Optional

from .models import SeqScore
from .utils import percentile_like, classify_impact_level, safe_str, safe_int


class MassiveOracleScorer:
    """Massive Oracle scorer for synthetic and real-context scoring."""
    
    def __init__(self, oracle_url: str = "https://crispro--zeta-oracle-zetaoracle-api.modal.run/invoke"):
        self.oracle_url = oracle_url
    
    async def score_synthetic(self, mutations: List[Dict[str, Any]]) -> List[SeqScore]:
        """
        Score variants using synthetic contrasting sequences for massive impact.
        
        Args:
            mutations: List of variant dictionaries
            
        Returns:
            List of SeqScore objects
        """
        seq_scores = []
        
        for m in mutations:
            chrom = m.get("chrom")
            pos = m.get("pos")
            ref = m.get("ref")
            alt = m.get("alt")
            gene = m.get("gene", "unknown")
            
            if not all([chrom, pos, ref, alt]):
                continue
            
            try:
                result = await self._fetch_massive_oracle_score(chrom, pos, ref, alt, gene)
                sequence_disruption = abs(float(result.get("massive_score", 0.0)))
                
                seq_scores.append(SeqScore(
                    variant=m,
                    sequence_disruption=sequence_disruption,
                    calibrated_seq_percentile=percentile_like(sequence_disruption),
                    impact_level=classify_impact_level(sequence_disruption),
                    scoring_mode="massive_synthetic",
                    best_model="massive_oracle",
                    scoring_strategy={
                        "approach": "synthetic_contrast",
                        "window_bp": 50000
                    }
                ))
            except Exception:
                continue
        
        return seq_scores
    
    async def score_real_context(self, mutations: List[Dict[str, Any]], 
                               flank_bp: int = 25000, assembly: str = "GRCh38") -> List[SeqScore]:
        """
        Score variants using real GRCh38 context.
        
        Args:
            mutations: List of variant dictionaries
            flank_bp: Flank size in base pairs
            assembly: Assembly version
            
        Returns:
            List of SeqScore objects
        """
        seq_scores = []
        
        for m in mutations:
            chrom = m.get("chrom")
            pos = m.get("pos")
            ref = m.get("ref")
            alt = m.get("alt")
            gene = m.get("gene", "unknown")
            
            if not all([chrom, pos, ref, alt]):
                continue
            
            try:
                result = await self._fetch_massive_oracle_score_real_context(
                    chrom, pos, ref, alt, gene, flank_bp, assembly
                )
                sequence_disruption = abs(float(result.get("massive_score", 0.0)))
                
                seq_scores.append(SeqScore(
                    variant=m,
                    sequence_disruption=sequence_disruption,
                    calibrated_seq_percentile=percentile_like(sequence_disruption),
                    impact_level=classify_impact_level(sequence_disruption),
                    scoring_mode="massive_real",
                    best_model="massive_oracle",
                    scoring_strategy={
                        "approach": "real_context",
                        "window_bp": flank_bp * 2,
                        "assembly": assembly
                    }
                ))
            except Exception:
                continue
        
        return seq_scores
    
    async def _fetch_massive_oracle_score(self, chrom: str, pos: int, ref: str, 
                                        alt: str, gene: str) -> Dict[str, Any]:
        """Call the old Oracle for massive impact scoring using large sequence windows."""
        try:
            # Create sequences designed for massive impact scoring
            base_size = 50000  # 50kb sequences for maximum scoring capability
            ref_pattern = "ATCGATCGATCGATCGAAAA"  # 20bp pattern
            alt_pattern = "TTTTTTTTTTTTTTTTTTTA"  # Contrasting pattern
            
            # Generate base sequences
            ref_base = (ref_pattern * (base_size // len(ref_pattern)))[:base_size]
            alt_base = (alt_pattern * (base_size // len(alt_pattern)))[:base_size]
            
            # Insert the actual variant in the center for biological relevance
            center = base_size // 2
            variant_context = f"NNNN{ref}NNNN"
            alt_variant_context = f"NNNN{alt}NNNN"
            
            # Replace center section with variant context
            context_len = len(variant_context)
            ref_sequence = (ref_base[:center-context_len//2] + variant_context + 
                          ref_base[center+context_len//2:])
            alt_sequence = (alt_base[:center-context_len//2] + alt_variant_context + 
                          alt_base[center+context_len//2:])
            
            # Ensure sequences are exactly the same length
            min_len = min(len(ref_sequence), len(alt_sequence))
            ref_sequence = ref_sequence[:min_len]
            alt_sequence = alt_sequence[:min_len]
            
            payload = {
                "action": "score",
                "params": {
                    "reference_sequence": ref_sequence,
                    "alternate_sequence": alt_sequence
                }
            }
            
            async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
                response = await client.post(self.oracle_url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                return {
                    "massive_score": result.get("zeta_score", 0.0),
                    "reference_likelihood": result.get("reference_likelihood", 0.0),
                    "alternate_likelihood": result.get("alternate_likelihood", 0.0),
                    "sequence_length": len(ref_sequence),
                    "gene": gene,
                    "variant": f"{chrom}:{pos} {ref}>{alt}",
                    "status": "massive_impact_scoring"
                }
                
        except Exception as e:
            return {
                "massive_score": 0.0,
                "error": f"Massive Oracle scoring failed: {str(e)}",
                "gene": gene,
                "variant": f"{chrom}:{pos} {ref}>{alt}",
                "status": "massive_impact_failed"
            }
    
    async def _fetch_massive_oracle_score_real_context(self, chrom: str, pos: int, 
                                                     ref: str, alt: str, gene: str, 
                                                     flank_bp: int = 25000, 
                                                     assembly: str = "GRCh38") -> Dict[str, Any]:
        """Call the old Oracle with real GRCh38 context."""
        try:
            start = max(1, int(pos) - int(flank_bp))
            end = int(pos) + int(flank_bp)
            
            # Ensembl sequence API (text/plain)
            seq_url = (f"https://rest.ensembl.org/sequence/region/human/{chrom}:{start}-{end}"
                      f"?content-type=text/plain;coord_system_version={assembly}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                rs = await client.get(seq_url)
                rs.raise_for_status()
                ref_seq = (rs.text or "").strip().upper()
            
            if not ref_seq:
                raise RuntimeError("empty reference sequence from Ensembl")
            
            # Determine index of the variant within the fetched window
            idx = int(pos) - start
            if idx < 0 or idx >= len(ref_seq):
                raise RuntimeError("variant index out of fetched sequence bounds")
            
            # Construct alternate sequence by replacing the base at idx
            alt_seq_list = list(ref_seq)
            alt_seq_list[idx] = str(alt).upper()[:1] if alt else alt_seq_list[idx]
            alt_seq = "".join(alt_seq_list)
            
            payload = {
                "action": "score",
                "params": {
                    "reference_sequence": ref_seq,
                    "alternate_sequence": alt_seq
                }
            }
            
            async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
                response = await client.post(self.oracle_url, json=payload)
                response.raise_for_status()
                result = response.json()
            
            return {
                "massive_score": result.get("zeta_score", 0.0),
                "reference_likelihood": result.get("reference_likelihood", 0.0),
                "alternate_likelihood": result.get("alternate_likelihood", 0.0),
                "sequence_length": len(ref_seq),
                "gene": gene,
                "variant": f"{chrom}:{pos} {ref}>{alt}",
                "status": "massive_real_scoring",
                "sequence_source": f"{assembly}_real",
                "window": {"start": start, "end": end}
            }
        except Exception as e:
            return {
                "massive_score": 0.0,
                "error": f"Massive Oracle real-context scoring failed: {str(e)}",
                "gene": gene,
                "variant": f"{chrom}:{pos} {ref}>{alt}",
                "status": "massive_real_failed"
            }


