"""Explainable opportunity scoring for tofu suya and Kafi soy yoghurt.

The weighted score follows Amina's scoring framework:

    weighted = sum(score_i * weight_i) / 5

A row is rankable only when every criterion has a score from 1 to 5.
Evidence confidence is reported beside the score. A high score never
promotes a low-confidence row onto the launch shortlist.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SCORE_SPECS = (
    ("Demand potential", "Demand_Score_1to5", 30),
    ("Affordability / price fit", "Affordability_Score_1to5", 25),
    ("Channel access", "Channel_Score_1to5", 20),
    ("Supply & distribution", "Supply_Distribution_Score_1to5", 15),
    ("Market gap / competition", "Market_Gap_Score_1to5", 10),
)

CONFIDENCE_RANK = {"High": 3, "Medium": 2, "Low": 1}
SHORTLIST_CONFIDENCE = "High"

def clean_confidence(value) -> str:
    """Return High, Medium, Low, or an empty string. Blank cells are not a level."""
    try:
        if value is None or pd.isna(value):
            return ""
    except TypeError:
        if value is None:
            return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "<na>"}:
        return ""
    return text if text in CONFIDENCE_RANK else ""


@dataclass(frozen=True)
class Criterion:
    name: str
    column: str
    weight: int


def criteria_from_weights(weights: dict[str, int] | None = None) -> tuple[Criterion, ...]:
    """Build the five criteria. Missing names fall back to the framework defaults."""
    defaults = {name: weight for name, _column, weight in SCORE_SPECS}
    chosen = dict(defaults if weights is None else {**defaults, **weights})
    return tuple(
        Criterion(name, column, int(chosen[name]))
        for name, column, _default in SCORE_SPECS
    )


def weight_total(criteria: tuple[Criterion, ...]) -> int:
    return sum(item.weight for item in criteria)


def _numeric(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def valid_score(value) -> int | None:
    """Return an integer score in 1..5, or None when the cell cannot be used."""
    number = _numeric(value)
    if number is None:
        return None
    if number != int(number):
        return None
    score = int(number)
    if score < 1 or score > 5:
        return None
    return score


def contribution_points(score: int, weight: int) -> float:
    return score * weight / 5


def score_row(row: pd.Series, criteria: tuple[Criterion, ...]) -> dict:
    """Score one opportunity. The weighted total stays empty until every score is valid."""
    parts: list[dict] = []
    missing: list[str] = []
    invalid: list[str] = []
    for item in criteria:
        raw = row.get(item.column)
        score = valid_score(raw)
        present = _numeric(raw) is not None or (
            isinstance(raw, str) and raw.strip() != ""
        )
        if score is None:
            if present:
                invalid.append(item.name)
            else:
                missing.append(item.name)
            parts.append(
                {
                    "criterion": item.name,
                    "column": item.column,
                    "weight": item.weight,
                    "score": None,
                    "points": None,
                }
            )
            continue
        parts.append(
            {
                "criterion": item.name,
                "column": item.column,
                "weight": item.weight,
                "score": score,
                "points": contribution_points(score, item.weight),
            }
        )

    rankable = not missing and not invalid
    total = round(sum(part["points"] for part in parts), 1) if rankable else None
    confidence = clean_confidence(row.get("Evidence_Confidence"))

    if not rankable:
        status = "Not rankable"
    elif confidence == SHORTLIST_CONFIDENCE:
        status = "Shortlist"
    elif confidence == "Medium":
        status = "Compare with care"
    else:
        status = "Illustrative only"

    return {
        "parts": parts,
        "missing": missing,
        "invalid": invalid,
        "rankable": rankable,
        "weighted_score": total,
        "confidence": confidence,
        "decision_status": status,
    }


def prepare_opportunities(
    frame: pd.DataFrame,
    criteria: tuple[Criterion, ...] | None = None,
) -> pd.DataFrame:
    """Add weighted score, rank, and decision status. Does not write the CSV."""
    criteria = criteria or criteria_from_weights()
    working = frame.copy()
    scored = [score_row(row, criteria) for _, row in working.iterrows()]
    working["Weighted_Opportunity_Score_0to100"] = [
        item["weighted_score"] for item in scored
    ]
    working["Decision_Status"] = [item["decision_status"] for item in scored]
    working["Rankable"] = [item["rankable"] for item in scored]
    working["Score_Breakdown"] = [item["parts"] for item in scored]
    working["Missing_Criteria"] = [item["missing"] for item in scored]
    working["Invalid_Criteria"] = [item["invalid"] for item in scored]

    ranks = pd.Series(pd.NA, index=working.index, dtype="Float64")
    rankable_mask = working["Rankable"]
    if rankable_mask.any():
        ranks.loc[rankable_mask] = (
            working.loc[rankable_mask, "Weighted_Opportunity_Score_0to100"]
            .rank(method="min", ascending=False)
            .astype(int)
        )
    working["Rank"] = ranks
    return working


def ranked_view(frame: pd.DataFrame) -> pd.DataFrame:
    """Rankable rows first, highest score first. Ties keep a stable city/product order."""
    prepared = frame if "Rankable" in frame.columns else prepare_opportunities(frame)
    ordered = prepared.sort_values(
        by=[
            "Rankable",
            "Weighted_Opportunity_Score_0to100",
            "City",
            "Product",
            "Customer_Segment",
            "Opportunity_ID",
        ],
        ascending=[False, False, True, True, True, True],
        na_position="last",
    )
    return ordered.reset_index(drop=True)


def shortlist(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows a business could act on: complete scores and high evidence confidence."""
    prepared = frame if "Decision_Status" in frame.columns else prepare_opportunities(frame)
    chosen = prepared[prepared["Decision_Status"] == "Shortlist"]
    return ranked_view(chosen)


def explain_opportunity(row: pd.Series, population: pd.DataFrame) -> dict:
    """Plain-language reason for one rank, including ties and withheld criteria."""
    parts = list(row["Score_Breakdown"])
    score = row["Weighted_Opportunity_Score_0to100"]
    confidence = clean_confidence(row.get("Evidence_Confidence")) or "not recorded"
    label = (
        f"{row['City']} · {row['Product']} · {row['Customer_Segment']}"
    )

    if not bool(row["Rankable"]):
        missing = list(row["Missing_Criteria"])
        invalid = list(row["Invalid_Criteria"])
        reasons = []
        if missing:
            reasons.append("missing " + ", ".join(missing))
        if invalid:
            reasons.append("invalid " + ", ".join(invalid))
        detail = "; ".join(reasons) if reasons else "scores are incomplete"
        return {
            "label": label,
            "headline": f"{label} is not ranked.",
            "sentences": [
                f"The weighted score stays blank because {detail}.",
                "The model refuses a partial total, so a strong score on one criterion cannot disguise a gap on another.",
                f"Evidence confidence is {confidence}.",
            ],
            "parts": parts,
        }

    same_score = population[
        population["Rankable"]
        & (population["Weighted_Opportunity_Score_0to100"] == score)
    ]
    tied = len(same_score) - 1
    rank = int(row["Rank"])
    sentences = [
        f"{label} scores {score:.1f} out of 100 and shares rank {rank}.",
    ]
    if tied:
        noun = "opportunity" if tied == 1 else "opportunities"
        sentences.append(
            f"It is tied with {tied} other {noun}. "
            "The tie is left as a tie. Soybean tonnage is not used to break it."
        )
    else:
        sentences.append("No other opportunity in the current filter has this score.")

    ordered_parts = sorted(parts, key=lambda part: part["points"], reverse=True)
    leader = ordered_parts[0]
    sentences.append(
        f"The largest contribution is {leader['criterion']}: "
        f"score {leader['score']} of 5, weight {leader['weight']}, "
        f"{leader['points']:.1f} points."
    )
    breakdown = ", ".join(
        f"{part['criterion']} {part['points']:.1f}" for part in ordered_parts
    )
    sentences.append(f"Point split: {breakdown}.")

    status = row["Decision_Status"]
    if status == "Shortlist":
        sentences.append(
            "Evidence confidence is High, so this row can sit on the launch shortlist."
        )
    elif status == "Compare with care":
        sentences.append(
            "Evidence confidence is Medium. Use the rank to compare options, and keep the remaining gaps visible."
        )
    else:
        sentences.append(
            f"Evidence confidence is {confidence}. "
            "This rank is illustrative only and stays off the launch shortlist."
        )

    notes = str(row.get("Assumptions_and_Data_Gaps") or "").strip()
    if notes:
        sentences.append(notes)
    return {
        "label": label,
        "headline": sentences[0],
        "sentences": sentences,
        "parts": parts,
    }


def result_summary(frame: pd.DataFrame) -> str:
    """One paragraph a business reader can use without opening the table."""
    prepared = frame if "Rankable" in frame.columns else prepare_opportunities(frame)
    total = len(prepared)
    rankable = prepared[prepared["Rankable"]] if total else prepared
    launch = prepared[prepared["Decision_Status"] == "Shortlist"] if total else prepared
    if total == 0:
        return "No rows match the current filters."
    if rankable.empty:
        return (
            f"None of the {total} product, city, and segment rows can be ranked yet. "
            "Each row needs all five scores before a weighted total is calculated. "
            "The launch shortlist is empty."
        )

    top = float(rankable["Weighted_Opportunity_Score_0to100"].max())
    leaders = rankable[rankable["Weighted_Opportunity_Score_0to100"] == top]
    cities = ", ".join(sorted(leaders["City"].unique()))
    products = " and ".join(sorted(leaders["Product"].unique()))
    segments = "; ".join(sorted(leaders["Customer_Segment"].unique()))
    launch_note = (
        f"{len(launch)} row{'s' if len(launch) != 1 else ''} can go on the launch shortlist."
        if len(launch)
        else "Nothing is on the launch shortlist, because evidence confidence is not High."
    )
    return (
        f"{len(rankable)} of {total} rows are rankable. "
        f"The top score is {top:.1f}. It is shared by {products} "
        f"for {segments} in {cities}. "
        f"{launch_note}"
    )
