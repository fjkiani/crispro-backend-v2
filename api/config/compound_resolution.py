"""
Compound Resolution Configuration

Configuration settings for PubChem compound alias resolution.

Author: CrisPRO Platform
Date: November 5, 2025
"""

from pydantic import BaseSettings
from typing import Optional


class CompoundResolutionConfig(BaseSettings):
    """
    Configuration for compound alias resolution.
    
    Environment variables can be set with COMPOUND_RESOLUTION_ prefix.
    
    Example:
        COMPOUND_RESOLUTION_ENABLE_ALIAS_RESOLUTION=true
        COMPOUND_RESOLUTION_PUBCHEM_MAX_RETRIES=3
    """
    
    # PubChem API settings
    pubchem_base_url: str = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    pubchem_timeout: int = 5
    pubchem_max_retries: int = 2
    
    # Rate limiting
    requests_per_second: int = 5
    delay_between_requests: float = 0.2  # 200ms = 5 requests/second
    
    # Caching
    cache_ttl_seconds: int = 86400  # 24 hours
    cache_max_size: int = 10000
    
    # Feature flags
    enable_alias_resolution: bool = True
    fallback_to_original_on_failure: bool = True
    
    # Cache warming (common compounds to pre-populate)
    warm_cache_on_startup: bool = True
    common_compounds: list[str] = [
        # Existing 10 compounds
        "Vitamin D",
        "Vitamin C",
        "Curcumin",
        "Resveratrol",
        "Omega-3 fatty acids",
        "Green Tea Extract",
        "Quercetin",
        "Genistein",
        "Lycopene",
        "Beta-carotene",
        
        # Additional vitamins & minerals
        "Vitamin B6",
        "Vitamin B9",
        "Folic Acid",
        "Vitamin K2",
        "Vitamin E",
        "Vitamin A",
        "Vitamin B12",
        "Selenium",
        "Zinc",
        "Magnesium",
        "Calcium",
        "Iron",
        "Copper",
        "Manganese",
        
        # Polyphenols & flavonoids
        "Fisetin",
        "Apigenin",
        "Luteolin",
        "Kaempferol",
        "EGCG",
        "Epicatechin",
        "Catechin",
        "Proanthocyanidins",
        "Anthocyanins",
        
        # Carotenoids
        "Astaxanthin",
        "Lutein",
        "Zeaxanthin",
        "Beta-cryptoxanthin",
        
        # Other plant compounds
        "Sulforaphane",
        "Indole-3-carbinol",
        "DIM",
        "Ellagic acid",
        "Gallic acid",
        "Chlorogenic acid",
        "Ferulic acid",
        "Caffeic acid",
        
        # Herbs & adaptogens
        "Ashwagandha",
        "Rhodiola",
        "Ginseng",
        "Turmeric",
        "Ginger",
        "Ginkgo biloba",
        "Milk thistle",
        "Echinacea",
        "Garlic",
        "Onion",
        
        # Amino acids & derivatives
        "NAC",
        "N-acetylcysteine",
        "Glutathione",
        "L-Carnitine",
        "CoQ10",
        "Alpha-lipoic acid",
        
        # Omega fatty acids
        "Omega-6 fatty acids",
        "EPA",
        "DHA",
        "ALA",
        
        # Other common supplements
        "Melatonin",
        "Probiotics",
        "Prebiotics",
        "Fiber",
        "Choline",
        "Inositol",
        "Pterostilbene",
        "Piceatannol",
        "Urolithin A",
        "Spermidine",
        "Nicotinamide",
        "NMN",
        "Berberine",
        "Metformin",
        
        # Food compounds (mapped to active ingredients)
        "Broccoli",
        "Spinach",
        "Blueberries",
        "Green tea",
        "Red wine",
        "Olive oil",
        "Fish oil",
        "Flaxseed",
        "Chia seeds",
        "Walnuts",
        "Almonds",
        "Pomegranate",
        "Grapes",
        "Tomatoes",
        "Carrots",
        "Sweet potatoes",
        "Mushrooms",
        
        # Cancer research compounds
        "DHA",
        "EPA",
        "Rapamycin",
        "Metformin",
        "Aspirin",
        "Ibuprofen",
        "Celecoxib",
        
        # Total: 100+ compounds
    ]
    
    class Config:
        env_prefix = "COMPOUND_RESOLUTION_"
        case_sensitive = False


# Global config instance
_config: Optional[CompoundResolutionConfig] = None


def get_config() -> CompoundResolutionConfig:
    """
    Get or create the global CompoundResolutionConfig instance.
    
    Returns:
        CompoundResolutionConfig singleton instance
    """
    global _config
    if _config is None:
        _config = CompoundResolutionConfig()
    return _config

