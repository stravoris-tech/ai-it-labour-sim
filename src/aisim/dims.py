"""Model dimensions: the index sets and the maps between them.

This is structure, not parameters: it mirrors the module constants of ``phase7_sim.py`` (lines 20-33) and the
unit table in its docstring. Spec: 00 "Stocks, flows and key auxiliaries" and 06b (units and employers).

Units (employment units)          employer   located   hires from
  IH     consumer in-house        IH         Onshore   Onshore pool
  GCC    consumer captive         GCC        India     India pool
  VI     Indian IT offshore       OIT        India     India pool
  OV     Indian IT onsite visa    OIT        Onshore   India pool (visa holders)
  OL     Indian IT onsite local   OIT        Onshore   Onshore pool
  SI_IN  global SI, India centre  GSI        India     India pool
  SI_ON  global SI, onshore       GSI        Onshore   Onshore pool
  BQ     boutique                 BQ         Onshore   Onshore pool
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

UNITS: Final = ("IH", "GCC", "VI", "OV", "OL", "SI_IN", "SI_ON", "BQ")
EMPLOYERS: Final = ("IH", "GCC", "OIT", "GSI", "BQ")
VENDORS: Final = ("OIT", "GSI", "BQ")
REGIONS: Final = ("IN", "ON")
LEVELS: Final = ("J", "M", "S")
SECTORS: Final = ("FIN", "LEG", "MED", "GOV", "MFG", "LOG", "RET")
WTYPES: Final = ("APP", "DATA", "SEC", "GOVN", "SUP", "EUS")
TYPES: Final = ("FP", "TM", "MS", "SA", "OB")
EFFORT: Final = ("TM", "SA")

EMP_OF: Final[Mapping[str, str]] = {
    "IH": "IH",
    "GCC": "GCC",
    "VI": "OIT",
    "OV": "OIT",
    "OL": "OIT",
    "SI_IN": "GSI",
    "SI_ON": "GSI",
    "BQ": "BQ",
}
"""Employer of each unit."""

POOL: Final[Mapping[str, str]] = {
    "IH": "ON",
    "GCC": "IN",
    "VI": "IN",
    "OV": "IN",
    "OL": "ON",
    "SI_IN": "IN",
    "SI_ON": "ON",
    "BQ": "ON",
}
"""Labour pool each unit hires from. OV hires from the India pool."""

LOC: Final[Mapping[str, str]] = {
    "IH": "ON",
    "GCC": "IN",
    "VI": "IN",
    "OV": "ON",
    "OL": "ON",
    "SI_IN": "IN",
    "SI_ON": "ON",
    "BQ": "ON",
}
"""Location of each unit. OV is located onshore."""

EMP_POOL: Final[Mapping[str, str]] = {"IH": "ON", "GCC": "IN", "OIT": "IN", "GSI": "IN", "BQ": "ON"}
"""Main labour pool of each employer."""

SWITCHERS: Final = ("IH", "GCC", "VI", "OL", "SI_IN", "SI_ON", "BQ")
"""Units whose staff switch jobs. Visa holders (OV) do not switch."""
