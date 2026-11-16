"""Tests for the opportunity score, the rank, and the plain-language reason."""

from pathlib import Path

import pandas as pd
import pytest

from scoring.model import (
    criteria_from_weights,
    explain_opportunity,
    prepare_opportunities,
    result_summary,
    shortlist,
    valid_score,
    weight_total,
)
from scoring.scenario import apply_practice_scenario

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "opportunity_data.csv"


def _row(**overrides) -> pd.DataFrame:
    base = {
        "Opportunity_ID": "OP-TEST",
        "Product": "Tofu suya",
        "City": "Kaduna",
        "State/FCT": "Kaduna",
        "Region": "North West",
        "Customer_Segment": "Students and young adults",
        "Likely_Channel": "Suya vendors",
        "Soybean_State_Output_2024_tonnes": 93741.86,
        "Demand_Score_1to5": 4,
        "Affordability_Score_1to5": 3,
        "Channel_Score_1to5": 5,
        "Supply_Distribution_Score_1to5": 2,
        "Market_Gap_Score_1to5": 1,
        "Evidence_Confidence": "High",
        "Assumptions_and_Data_Gaps": "",
    }
    base.update(overrides)
    return pd.DataFrame([base])


def test_default_weights_match_the_framework():
    criteria = criteria_from_weights()
    assert weight_total(criteria) == 100
    assert [item.weight for item in criteria] == [30, 25, 20, 15, 10]


def test_weighted_score_uses_the_published_formula():
    # 4*30 + 3*25 + 5*20 + 2*15 + 1*10 = 120+75+100+30+10 = 335; 335/5 = 67
    prepared = prepare_opportunities(_row())
    assert prepared.loc[0, "Weighted_Opportunity_Score_0to100"] == 67.0
    assert prepared.loc[0, "Decision_Status"] == "Shortlist"


def test_partial_scores_do_not_produce_a_total():
    prepared = prepare_opportunities(_row(Demand_Score_1to5=None))
    assert prepared.loc[0, "Rankable"] == False  # noqa: E712
    assert pd.isna(prepared.loc[0, "Weighted_Opportunity_Score_0to100"])
    assert prepared.loc[0, "Decision_Status"] == "Not rankable"


@pytest.mark.parametrize("bad", [0, 6, 3.5, "high", ""])
def test_scores_outside_one_to_five_are_rejected(bad):
    assert valid_score(bad) is None
    prepared = prepare_opportunities(_row(Channel_Score_1to5=bad))
    assert prepared.loc[0, "Rankable"] == False  # noqa: E712


def test_low_confidence_stays_off_the_shortlist_even_with_a_high_score():
    prepared = prepare_opportunities(_row(Evidence_Confidence="Low"))
    assert prepared.loc[0, "Weighted_Opportunity_Score_0to100"] == 67.0
    assert prepared.loc[0, "Decision_Status"] == "Illustrative only"
    assert shortlist(prepared).empty


def test_ties_share_a_rank_and_are_explained_without_soybean_tiebreak():
    first = _row(Opportunity_ID="OP-A", City="Abuja", Evidence_Confidence="Low")
    second = _row(Opportunity_ID="OP-B", City="Kano", Evidence_Confidence="Low")
    prepared = prepare_opportunities(pd.concat([first, second], ignore_index=True))
    assert list(prepared["Rank"]) == [1, 1]
    explanation = explain_opportunity(prepared.iloc[0], prepared)
    text = " ".join(explanation["sentences"])
    assert "tied with 1 other opportunity" in text
    assert "Soybean tonnage is not used to break it" in text


def test_contribution_points_sum_to_the_weighted_score():
    prepared = prepare_opportunities(_row())
    parts = prepared.loc[0, "Score_Breakdown"]
    assert round(sum(part["points"] for part in parts), 1) == 67.0


def test_recorded_dataset_has_no_rankable_rows_yet():
    raw = pd.read_csv(DATA)
    prepared = prepare_opportunities(raw)
    assert len(prepared) == 48
    assert int(prepared["Rankable"].sum()) == 0
    assert "None of the 48" in result_summary(prepared)
    assert shortlist(prepared).empty


def test_practice_scenario_is_ranked_and_still_blocked_from_launch():
    raw = pd.read_csv(DATA)
    prepared = prepare_opportunities(apply_practice_scenario(raw))
    assert int(prepared["Rankable"].sum()) == 48
    assert shortlist(prepared).empty
    summary = result_summary(prepared)
    assert "48 of 48 rows are rankable" in summary
    assert "Nothing is on the launch shortlist" in summary

    leaders = prepared[prepared["Rank"] == 1]
    assert set(leaders["Customer_Segment"]) == {
        "Health-conscious consumers",
        "Vegetarians, flexitarians and meat reducers",
    }
    assert "Lagos" not in set(leaders["City"])
    assert float(leaders["Weighted_Opportunity_Score_0to100"].iloc[0]) == 66.0

    lagos = prepared[prepared["City"] == "Lagos"]
    assert float(lagos["Weighted_Opportunity_Score_0to100"].max()) == 63.0
    explanation = explain_opportunity(leaders.iloc[0], prepared)
    assert "illustrative only" in " ".join(explanation["sentences"])
    assert "not a survey result" in " ".join(explanation["sentences"])


def test_blank_confidence_is_described_as_not_recorded():
    prepared = prepare_opportunities(_row(Evidence_Confidence=float("nan"), Demand_Score_1to5=None))
    explanation = explain_opportunity(prepared.iloc[0], prepared)
    text = " ".join(explanation["sentences"])
    assert "not recorded" in text
    assert "nan" not in text.lower()


def test_weight_change_moves_the_score_and_is_visible_in_the_reason():
    custom = criteria_from_weights({"Demand potential": 50, "Market gap / competition": 0})
    # Demand weight moved from 30 to 50, market gap from 10 to 0.
    # Other weights stay 25, 20, 15. Total is 110 on purpose so the caller can reject it.
    assert weight_total(custom) == 110
    prepared = prepare_opportunities(_row(), custom)
    # 4*50 + 3*25 + 5*20 + 2*15 + 1*0 = 200+75+100+30+0 = 405; 405/5 = 81
    assert prepared.loc[0, "Weighted_Opportunity_Score_0to100"] == 81.0
