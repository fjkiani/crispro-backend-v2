"""
Drug Mapping: Drug-to-pathway mapping utilities.
"""
from typing import Dict
from .panel_config import DEFAULT_MM_PANEL


def get_pathway_weights_for_drug(drug_name: str) -> Dict[str, float]:
	"""Get pathway weights for a specific drug."""
	for drug in DEFAULT_MM_PANEL:
		if drug["name"] == drug_name:
			return drug.get("pathway_weights", {})
	return {}


def get_pathway_weights_for_gene(gene_symbol: str) -> Dict[str, float]:
	"""Get pathway weights for a gene (used to aggregate sequence impact by pathway).

	Minimal MM mapping to unblock pathway signal:
	- MAPK drivers (BRAF/KRAS/NRAS) → ras_mapk
	- TP53 and related → tp53
	Extend as needed per disease.
	"""
	if not gene_symbol:
		return {}
	g = gene_symbol.strip().upper()
	if g in {"BRAF", "KRAS", "NRAS", "MAP2K1", "MAPK1"}:
		return {"ras_mapk": 1.0}
	# Map DNA repair/HR genes to tp53 pathway bucket to enable non-zero pathway signal
	if g in {"TP53", "MDM2", "ATM", "ATR", "CHEK2", "BRCA1", "BRCA2", "PTEN", "RAD51"}:
		return {"tp53": 1.0}
	return {}


def get_drug_moa(drug_name: str) -> str:
	"""Get mechanism of action for a specific drug."""
	for drug in DEFAULT_MM_PANEL:
		if drug["name"] == drug_name:
			return drug.get("moa", "")
	return ""


