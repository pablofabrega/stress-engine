"""Shared instrument reference data used across risk, scenario, and portfolio analytics.

Kept in a dependency-free leaf module so both the risk and portfolio packages can import it
without creating a circular import between them.
"""

from __future__ import annotations

# Single source of truth for fixed-income modified-duration estimates (years), keyed by ticker.
# Used for DV01 approximations in the hedge engine, hypothetical rate shocks, and portfolio DV01.
FIXED_INCOME_DURATIONS: dict[str, float] = {
    "BND": 6.4,
    "AGG": 6.2,
    "GOVT": 6.0,
    "TLT": 16.8,
    "VGLT": 16.5,
    "IEF": 7.5,
    "VGIT": 5.2,
    "SHY": 1.9,
    "VGSH": 1.9,
    "TIP": 6.9,
    "LQD": 8.5,
    "VCIT": 6.3,
    "IGIB": 6.5,
    "VCSH": 2.8,
    "IGSB": 2.6,
    "MUB": 5.8,
    "EMB": 7.2,
    "HYG": 3.8,
    "JNK": 3.6,
}
