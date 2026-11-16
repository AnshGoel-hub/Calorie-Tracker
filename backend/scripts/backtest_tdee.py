#!/usr/bin/env python3
"""Backtest the adaptive TDEE engine on simulated users and print numbers you can quote.

    python scripts/backtest_tdee.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tdee import backtest  # noqa: E402

SCENARIOS = [
    ("Baseline (formula off by 15%, 5% under-reporting)", {}),
    ("Perfect logging", {"logging_bias": 0.0}),
    ("Heavy under-reporting (-15%)", {"logging_bias": -0.15}),
    ("Sparse logging (50% of days)", {"log_prob": 0.5}),
    ("Noisy scale (sd 1.0 kg)", {"weight_noise_sd": 1.0}),
    ("Formula only off by 5%", {"prior_error": 0.05}),
]

if __name__ == "__main__":
    print(f"{'scenario':52} {'engine MAE':>11} {'formula MAE':>12} {'better':>8}")
    for name, kw in SCENARIOS:
        r = backtest(n=300, **kw)
        print(f"{name:52} {r['engine_mae_kcal']:>8} kcal {r['formula_mae_kcal']:>9} kcal {r['improvement_pct']:>7}%")
