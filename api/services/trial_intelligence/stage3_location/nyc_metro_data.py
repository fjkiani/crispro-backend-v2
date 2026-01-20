"""
NYC Metro Area Data

Defines what counts as "NYC metro" for Ayesha (zip 10029, willing to travel 50 miles).

Includes:
- NYC 5 boroughs (Manhattan, Brooklyn, Bronx, Queens, Staten Island)
- Northern NJ (within 50 miles)
- Southwest CT (Stamford, Bridgeport, New Haven)
"""

# NYC Metro cities (case-insensitive matching)
NYC_METRO_CITIES = [
    # NYC 5 Boroughs
    'New York', 'Manhattan', 'Brooklyn', 'Bronx', 'Queens', 'Staten Island',
    
    # Major NYC medical centers
    'East Harlem',  # Mount Sinai
    'Upper East Side',  # MSK, Weill Cornell
    'Midtown',  # NYU Langone
    'Lower Manhattan',  # NYU Downtown
    
    # Northern NJ (within 50 miles)
    'Jersey City', 'Newark', 'Hoboken', 'Paterson', 'Elizabeth',
    'Edison', 'Woodbridge', 'New Brunswick', 'Trenton',
    'Hackensack', 'Englewood', 'Fort Lee', 'Morristown',
    
    # Southwest CT (within 50 miles)
    'Stamford', 'Norwalk', 'Bridgeport', 'New Haven', 'Danbury',
    'Westport', 'Greenwich', 'Fairfield'
]

# Major NYC Cancer Centers (for exact matching)
NYC_MAJOR_CENTERS = [
    'Memorial Sloan Kettering',
    'MSK',
    'Sloan Kettering',
    'Mount Sinai',
    'Icahn School of Medicine',
    'NYU Langone',
    'New York University',
    'Weill Cornell',
    'Cornell',
    'Columbia University',
    'Columbia Presbyterian',
    'Montefiore',
    'Albert Einstein',
    'Hackensack Meridian',
    'Hackensack University Medical Center',
    'Rutgers Cancer Institute',
    'Yale Cancer Center',  # New Haven, CT
    'Yale-New Haven Hospital'
]

# States that are close enough to NYC (for fuzzy matching)
NYC_METRO_STATES = ['NY', 'NJ', 'CT']


