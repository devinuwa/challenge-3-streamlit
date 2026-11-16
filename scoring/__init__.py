"""Opportunity scoring used by the Streamlit dashboard and the tests."""

from scoring.model import (
    criteria_from_weights,
    explain_opportunity,
    prepare_opportunities,
    ranked_view,
    result_summary,
    shortlist,
)
from scoring.scenario import apply_practice_scenario

__all__ = [
    "apply_practice_scenario",
    "criteria_from_weights",
    "explain_opportunity",
    "prepare_opportunities",
    "ranked_view",
    "result_summary",
    "shortlist",
]
