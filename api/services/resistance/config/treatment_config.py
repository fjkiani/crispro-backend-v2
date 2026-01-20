"""
Treatment line and cross-resistance configuration constants.

Expert opinion multipliers for treatment line context and cross-resistance patterns.
"""

# Treatment line adjustment multipliers
# Source: Expert Opinion - Task 3 (clone evolution and treatment history)
TREATMENT_LINE_MULTIPLIERS = {
    1: 1.0,   # 1st line: use base probability
    2: 1.2,   # 2nd line: 20% increase (clone evolution)
    3: 1.4,   # 3rd+ line: 40% increase (heavily pre-treated)
}

# Cross-resistance multiplier
# Applied when same drug class was used previously
CROSS_RESISTANCE_MULTIPLIER = 1.3  # Same-class prior exposure

# Maximum probability cap
# Prevents probability from exceeding this value after adjustments
MAX_PROBABILITY_CAP = 0.95
