def calibrated_confidence(base, penalties=()): return max(0.0,min(1.0,base-sum(penalties)))
