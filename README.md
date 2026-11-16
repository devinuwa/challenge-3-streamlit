# Tofu suya and Kafi soy yoghurt — market opportunity tool

Hack the Fork Nigeria 2026, Challenge 3. This Streamlit app ranks where **tofu suya** and **Kafi soy yoghurt** are most likely to succeed among Nigerian cities and customer segments.

The question it answers: where is each product most likely to succeed commercially?

## Run it

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Check the scoring math without opening the app:

```powershell
python -m pytest
```

## What the score means

Five criteria come from `data/scoring_framework.csv`:

| Criterion | Weight |
| --- | ---: |
| Demand potential | 30 |
| Affordability / price fit | 25 |
| Channel access | 20 |
| Supply & distribution | 15 |
| Market gap / competition | 10 |

`weighted score = sum(score × weight) / 5`

A total appears only when every criterion is a whole number from 1 to 5. Evidence confidence sits beside the score. A row enters the **launch shortlist** only when that confidence is High. A high number with Low confidence stays illustrative.

The sidebar can switch between:

- **Practice scenario** — hypotheses so the ranking and the “why” text can be tested. Confidence stays Low. These numbers are not written into `data/opportunity_data.csv`.
- **Recorded evidence** — only the scores saved in that file. Today those cells are empty, so nothing is rankable until the team fills them.

State soybean tonnes for 2024 are shown as context. They are not city supply, and they are not used to break a tie.

## Roles

**Muhammad** builds the opportunity tool: the evaluation method, the scoring model, the rank, the reason for each rank, and the test that a reader can follow it. This repository’s app is that prototype.

**Amina** owns the evidence. She researches the Nigerian tofu, soy, and meat market; the customer groups; competing products including beef suya; preferences and willingness to pay; and the dataset. Verified facts stay separate from assumptions.

**Ibrahim** owns the commercial case: which segment can pay, which channel to use (suya spots, restaurants, or shops), how tofu suya’s cost compares with beef suya, which cities deserve a closer look, and the business recommendation that follows the ranking.

## Still open

The survey file has headers and no responses. Prices, outlet counts, and supplier notes are blank. Do not present the practice ranking as a launch decision.
