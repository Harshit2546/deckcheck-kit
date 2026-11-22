"""Checkers package: typed fact checkers per claim type.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: checkers/*.py
"""

from checkers.competition import check as check_competition
from checkers.funding import check as check_funding
from checkers.hiring import check as check_hiring
from checkers.market_size import check as check_market_size
from checkers.team_growth import check as check_team_growth
from checkers.team_size import check as check_team_size
from checkers.traction import check as check_traction

__all__ = [
    "check_competition",
    "check_funding",
    "check_hiring",
    "check_market_size",
    "check_team_growth",
    "check_team_size",
    "check_traction",
]
