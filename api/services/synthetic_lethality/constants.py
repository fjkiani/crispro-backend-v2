"""
Constants for Synthetic Lethality & Essentiality Agent.

Pathways, genes, drugs, and synthetic lethality relationships.
"""

# Variant consequences indicating truncation
TRUNCATING_CONSEQUENCES = {
    'stop_gained', 'nonsense', 'frameshift_variant',
    'splice_acceptor_variant', 'splice_donor_variant'
}

# Frameshift-specific consequences
FRAMESHIFT_CONSEQUENCES = {
    'frameshift_variant', 'frameshift_deletion',
    'frameshift_insertion', 'frame_shift_del', 'frame_shift_ins'
}

# Known hotspot mutations by gene
HOTSPOT_MUTATIONS = {
    'TP53': ['R175H', 'R248Q', 'R273H', 'R249S', 'G245S', 'R282W'],
    'KRAS': ['G12D', 'G12V', 'G12C', 'G13D', 'Q61H', 'Q61L'],
    'BRAF': ['V600E', 'V600K', 'K601E'],
    'PIK3CA': ['H1047R', 'E545K', 'E542K'],
    'NRAS': ['Q61R', 'Q61K', 'G12D'],
    'EGFR': ['L858R', 'T790M', 'C797S'],
}

# Gene to pathway mapping
GENE_PATHWAY_MAP = {
    # Base Excision Repair (BER)
    'MBD4': ['BER'], 'MUTYH': ['BER'], 'OGG1': ['BER'],
    'NTHL1': ['BER'], 'NEIL1': ['BER'], 'APEX1': ['BER'],
    
    # Homologous Recombination (HR)
    'BRCA1': ['HR'], 'BRCA2': ['HR'], 'ATM': ['HR', 'CHECKPOINT'],
    'ATR': ['HR', 'CHECKPOINT'], 'PALB2': ['HR'], 'RAD51': ['HR'],
    'CHEK1': ['HR', 'CHECKPOINT'], 'CHEK2': ['HR', 'CHECKPOINT'],
    'RAD51C': ['HR'], 'RAD51D': ['HR'], 'BRIP1': ['HR'],
    
    # Mismatch Repair (MMR)
    'MLH1': ['MMR'], 'MSH2': ['MMR'], 'MSH6': ['MMR'],
    'PMS2': ['MMR'], 'EPCAM': ['MMR'],
    
    # Checkpoint
    'TP53': ['CHECKPOINT'], 'CDKN2A': ['CHECKPOINT'],
    'RB1': ['CHECKPOINT'], 'MDM2': ['CHECKPOINT'],
    
    # MAPK
    'KRAS': ['MAPK'], 'BRAF': ['MAPK'], 'NRAS': ['MAPK'],
    'MAP2K1': ['MAPK'], 'MAPK1': ['MAPK'],
    
    # PI3K
    'PIK3CA': ['PI3K'], 'PTEN': ['PI3K'], 'AKT1': ['PI3K'],
    
    # PARP
    'PARP1': ['PARP'], 'PARP2': ['PARP'],
}

# Pathway definitions
PATHWAY_DEFINITIONS = {
    'BER': {
        'name': 'Base Excision Repair',
        'description': 'Repairs small base lesions from oxidation, alkylation',
        'genes': {'MBD4', 'MUTYH', 'OGG1', 'NTHL1', 'NEIL1', 'APEX1', 'XRCC1'}
    },
    'HR': {
        'name': 'Homologous Recombination',
        'description': 'Error-free repair of double-strand breaks',
        'genes': {'BRCA1', 'BRCA2', 'ATM', 'ATR', 'PALB2', 'RAD51', 'RAD51C', 'RAD51D'}
    },
    'MMR': {
        'name': 'Mismatch Repair',
        'description': 'Corrects DNA mismatches during replication',
        'genes': {'MLH1', 'MSH2', 'MSH6', 'PMS2'}
    },
    'CHECKPOINT': {
        'name': 'Cell Cycle Checkpoint',
        'description': 'G1/S and G2/M checkpoint control',
        'genes': {'TP53', 'CDKN2A', 'RB1', 'CHEK1', 'CHEK2', 'ATM', 'ATR'}
    },
    'PARP': {
        'name': 'PARP-mediated Repair',
        'description': 'Single-strand break repair pathway',
        'genes': {'PARP1', 'PARP2'}
    },
    'MAPK': {
        'name': 'MAPK Signaling',
        'description': 'RAS-RAF-MEK-ERK signaling cascade',
        'genes': {'KRAS', 'BRAF', 'NRAS', 'MAP2K1', 'MAPK1'}
    }
}

# Synthetic lethality relationships
# When pathway X is broken, cancer depends on pathway Y
SYNTHETIC_LETHALITY_MAP = {
    'HR': [
        {'pathway_id': 'PARP', 'name': 'PARP-mediated Repair', 'drugs': ['Olaparib', 'Niraparib', 'Rucaparib']}
    ],
    'BER': [
        {'pathway_id': 'HR', 'name': 'Homologous Recombination', 'drugs': ['Olaparib', 'Niraparib']},
        {'pathway_id': 'PARP', 'name': 'PARP-mediated Repair', 'drugs': ['Olaparib', 'Niraparib']}
    ],
    'CHECKPOINT': [
        {'pathway_id': 'ATR', 'name': 'ATR/CHK1 Pathway', 'drugs': ['Ceralasertib', 'Berzosertib']},
        {'pathway_id': 'WEE1', 'name': 'WEE1 Checkpoint', 'drugs': ['Adavosertib']}
    ],
    'MMR': [
        {'pathway_id': 'IO', 'name': 'Immune Checkpoint', 'drugs': ['Pembrolizumab', 'Nivolumab']}
    ]
}

# Drug catalog
DRUG_CATALOG = {
    'olaparib': {
        'name': 'Olaparib',
        'class': 'PARP_inhibitor',
        'target_genes': ['PARP1', 'PARP2'],
        'pathways': ['PARP', 'HR'],
        'mechanism': 'PARP inhibition → synthetic lethality with HR-deficient cells',
        'indications': ['ovarian_cancer', 'breast_cancer', 'prostate_cancer', 'pancreatic_cancer'],
        'fda_approved': True
    },
    'niraparib': {
        'name': 'Niraparib',
        'class': 'PARP_inhibitor',
        'target_genes': ['PARP1', 'PARP2'],
        'pathways': ['PARP', 'HR'],
        'mechanism': 'PARP inhibition (effective regardless of BRCA status in maintenance)',
        'indications': ['ovarian_cancer'],
        'fda_approved': True
    },
    'rucaparib': {
        'name': 'Rucaparib',
        'class': 'PARP_inhibitor',
        'target_genes': ['PARP1', 'PARP2', 'PARP3'],
        'pathways': ['PARP', 'HR'],
        'mechanism': 'Pan-PARP inhibition',
        'indications': ['ovarian_cancer', 'prostate_cancer'],
        'fda_approved': True
    },
    'ceralasertib': {
        'name': 'Ceralasertib',
        'class': 'ATR_inhibitor',
        'target_genes': ['ATR'],
        'pathways': ['ATR', 'CHECKPOINT'],
        'mechanism': 'ATR inhibition → replication stress → cell death',
        'indications': ['ovarian_cancer', 'lung_cancer'],
        'fda_approved': False
    },
    'adavosertib': {
        'name': 'Adavosertib',
        'class': 'WEE1_inhibitor',
        'target_genes': ['WEE1'],
        'pathways': ['WEE1', 'CHECKPOINT'],
        'mechanism': 'WEE1 inhibition → G2/M checkpoint abrogation',
        'indications': ['ovarian_cancer'],
        'fda_approved': False
    },
    'pembrolizumab': {
        'name': 'Pembrolizumab',
        'class': 'checkpoint_inhibitor',
        'target_genes': ['PDCD1'],
        'pathways': ['IO'],
        'mechanism': 'PD-1 blockade → T cell activation',
        'indications': ['melanoma', 'lung_cancer', 'msi_high'],
        'fda_approved': True
    }
}

# Pathway to drug mapping
PATHWAY_DRUG_MAP = {
    'PARP': ['olaparib', 'niraparib', 'rucaparib'],
    'HR': ['olaparib', 'niraparib'],
    'ATR': ['ceralasertib'],
    'WEE1': ['adavosertib'],
    'IO': ['pembrolizumab']
}


