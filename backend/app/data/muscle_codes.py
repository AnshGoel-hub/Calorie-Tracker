"""Muscle codes. GROUPS match MN in workouts.html; SUBS (id -> group) match MUSCLES in frontend/anatomy.js
(tests/test_muscles.py fails if they drift apart)."""
GROUPS = {"ch", "sh", "bi", "tr", "fo", "ab", "la", "tp", "lb", "gl", "qd", "ha", "ca"}
SUBS = {
    "pec_clav": "ch", "pec_ster": "ch", "pec_cost": "ch",
    "del_ant": "sh", "del_lat": "sh", "del_post": "sh", "cuff": "sh",
    "bi_long": "bi", "bi_short": "bi", "brach": "bi",
    "tr_long": "tr", "tr_lat": "tr", "tr_med": "tr",
    "fo_flex": "fo", "fo_ext": "fo", "brr": "fo",
    "ab_up": "ab", "ab_low": "ab", "obl": "ab",
    "trap_up": "tp", "trap_mid": "tp", "trap_low": "tp",
    "lat": "la", "teres": "la", "erector": "lb",
    "glute_max": "gl", "glute_med": "gl",
    "rf": "qd", "vl": "qd", "vm": "qd",
    "bf": "ha", "st": "ha", "sm": "ha",
    "gas_m": "ca", "gas_l": "ca", "sol": "ca", "tib": "ca",
}
