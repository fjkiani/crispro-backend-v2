"""Pathway Aggregation: Sequence score aggregation by pathway.

Key doctrine change:
- Pathway aggregation must not be dominated by percentile-like calibrations.
- Use raw sequence disruption as the primary signal.
- Allow *selective* hotspot lift for a small set of genes (TP53/BRAF/KRAS/NRAS) to support class selection.
- Apply conservative DDR missense gating to reduce PARP false positives on DDR-but-benign variants.

This module is RUO and designed for benchmarking stability.
"""

from typing import Any, Dict, List


HOTSPOT_GENES = {"TP53", "BRAF", "KRAS", "NRAS"}


def aggregate_pathways(seq_scores: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregate sequence scores by pathway.

    Args:
        seq_scores: list of dicts from DrugScorer.seq_score_to_dict

    Returns:
        pathway -> aggregated score
    """
    pathway_totals: Dict[str, float] = {}
    pathway_counts: Dict[str, int] = {}

    for score in seq_scores:
        if not isinstance(score, dict):
            continue

        pathway_weights = score.get("pathway_weights") or {}
        if not isinstance(pathway_weights, dict):
            continue

        variant = score.get("variant") or {}
        gene = str((variant.get("gene") or "")).strip().upper()
        consequence = str((variant.get("consequence") or "")).lower()

        # Raw disruption should be the primary signal for pathway aggregation.
        raw = float(score.get("sequence_disruption") or 0.0)
        pct = float(score.get("calibrated_seq_percentile") or 0.0)

        # Selective hotspot lift: allow a bounded lift for a small set of hotspot-heavy genes.
        # IMPORTANT: do NOT let percentile overwhelm raw (it was causing PARP always-on behavior).
        signal = raw
        if gene in HOTSPOT_GENES and pct >= 0.7:
            # bounded lift: enough to matter for pathway alignment, not enough to drown everything
            signal = max(signal, 0.5 * pct)

        for pathway, weight in pathway_weights.items():
            if not isinstance(weight, (int, float)):
                continue

            # Conservative DDR missense gating:
            # If variant is missense + low raw disruption, do not treat it as DDR-disrupting.
            if pathway == "ddr" and "missense" in consequence and raw < 0.02:
                continue

            pathway_totals[pathway] = pathway_totals.get(pathway, 0.0) + (signal * float(weight))
            pathway_counts[pathway] = pathway_counts.get(pathway, 0) + 1

    pathway_scores: Dict[str, float] = {}
    for pathway, total in pathway_totals.items():
        n = pathway_counts.get(pathway, 0)
        pathway_scores[pathway] = (total / n) if n else 0.0

    return pathway_scores
