"""Practice scores so the dashboard can show a ranking before fieldwork lands.

Every number here is a hypothesis. Nothing in this module is a survey result,
a price observation, or a supplier quote. The app must keep that label visible.
"""

from __future__ import annotations

import pandas as pd

# Segment hypotheses only. They are not demand measurements.
SEGMENT_DEMAND = {
    "Vegetarians, flexitarians and meat reducers": 4,
    "Health-conscious consumers": 4,
    "Students and young adults": 3,
    "Households / general consumers": 2,
}

# Rubric midpoint: price looks comparable only because no price has been observed.
AFFORDABILITY_SCORE = 3
# A channel is named on every row. Outlet counts are still missing, so this is a 3.
CHANNEL_SCORE = 3
# State soybean figures are context, not city supply. 3 means "feasible, unproven".
SUPPLY_WHEN_STATE_FIGURE_EXISTS = 3
SUPPLY_WHEN_STATE_FIGURE_MISSING = 2
# Beef suya and dairy yoghurt are known substitutes. Differentiation is unproven.
MARKET_GAP_SCORE = 3


def apply_practice_scenario(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with hypothesis scores. The source CSV is left untouched."""
    working = frame.copy()
    notes: list[str] = []
    demand_scores: list[int] = []
    supply_scores: list[int] = []

    for _, row in working.iterrows():
        segment = str(row["Customer_Segment"])
        if segment not in SEGMENT_DEMAND:
            raise KeyError(f"No practice demand hypothesis for segment: {segment}")
        demand = SEGMENT_DEMAND[segment]
        soy = row.get("Soybean_State_Output_2024_tonnes")
        has_soy = pd.notna(soy) and str(soy).strip() != ""
        supply = (
            SUPPLY_WHEN_STATE_FIGURE_EXISTS
            if has_soy
            else SUPPLY_WHEN_STATE_FIGURE_MISSING
        )
        demand_scores.append(demand)
        supply_scores.append(supply)
        soy_clause = (
            f"Supply {supply}/5 uses the state soybean figure only as context "
            f"({soy} tonnes). It is not city stock or a supplier quote."
            if has_soy
            else (
                f"Supply {supply}/5 is lower because this sheet has no verified "
                "state soybean figure. That is a data gap, not a finding that the state grows none."
            )
        )
        notes.append(
            " ".join(
                [
                    f"Demand {demand}/5 is a segment hypothesis for “{segment}”, not a survey result.",
                    f"Affordability {AFFORDABILITY_SCORE}/5 is the rubric midpoint because no comparable price is recorded.",
                    f"Channel {CHANNEL_SCORE}/5 reflects a named channel only. Outlet counts are missing.",
                    soy_clause,
                    (
                        f"Market gap {MARKET_GAP_SCORE}/5 treats beef suya or dairy yoghurt as a "
                        "strong substitute. A full competitor scan is still missing."
                    ),
                    "Practice scenario only. Do not present this score as market evidence.",
                ]
            )
        )

    working["Demand_Score_1to5"] = demand_scores
    working["Affordability_Score_1to5"] = AFFORDABILITY_SCORE
    working["Channel_Score_1to5"] = CHANNEL_SCORE
    working["Supply_Distribution_Score_1to5"] = supply_scores
    working["Market_Gap_Score_1to5"] = MARKET_GAP_SCORE
    working["Evidence_Confidence"] = "Low"
    working["Assumptions_and_Data_Gaps"] = notes
    working["Research_Notes"] = (
        "Practice scenario generated so the scoring tool can be tested. Not a market finding."
    )
    working["Score_Basis"] = "Practice assumption"
    return working
