"""Market opportunity dashboard for tofu suya and Kafi soy yoghurt.

Muhammad's prototype: a transparent scoring model, a ranked view, and a
plain-language reason for every rank. Recorded evidence and the practice
scenario are kept separate. The practice scenario never writes Amina's CSV.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scoring.model import (
    criteria_from_weights,
    explain_opportunity,
    prepare_opportunities,
    ranked_view,
    result_summary,
    valid_score,
    weight_total,
)
from scoring.scenario import apply_practice_scenario

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SCORE_COLUMNS = [item[1] for item in (
    ("Demand potential", "Demand_Score_1to5", 30),
    ("Affordability / price fit", "Affordability_Score_1to5", 25),
    ("Channel access", "Channel_Score_1to5", 20),
    ("Supply & distribution", "Supply_Distribution_Score_1to5", 15),
    ("Market gap / competition", "Market_Gap_Score_1to5", 10),
)]
CRITERION_NAMES = [
    "Demand potential",
    "Affordability / price fit",
    "Channel access",
    "Supply & distribution",
    "Market gap / competition",
]
PRODUCT_COLORS = {
    "Tofu suya": "#c45c26",
    "Kafi soy yoghurt": "#1f6b4a",
}


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name)


def base_table(mode: str) -> pd.DataFrame:
    raw = load_csv("opportunity_data.csv")
    if mode == "practice":
        return apply_practice_scenario(raw)
    raw["Score_Basis"] = "Recorded evidence"
    return raw


def init_state() -> None:
    if "mode" not in st.session_state:
        st.session_state.mode = "practice"
    if "editor_nonce" not in st.session_state:
        st.session_state.editor_nonce = 0
    if "table" not in st.session_state:
        st.session_state.table = base_table(st.session_state.mode)


def editor_key() -> str:
    return f"editor-{st.session_state.mode}-{st.session_state.editor_nonce}"


def set_mode(mode: str) -> None:
    if mode == st.session_state.mode:
        return
    st.session_state.mode = mode
    st.session_state.table = base_table(mode)
    st.session_state.editor_nonce += 1
    st.rerun()


def reset_table() -> None:
    st.session_state.table = base_table(st.session_state.mode)
    st.session_state.editor_nonce += 1
    st.rerun()


def apply_editor(edited: pd.DataFrame) -> None:
    """Copy workshop edits into the session table. Practice confidence stays Low."""
    if "Opportunity_ID" not in edited.columns:
        return
    current = st.session_state.table.set_index("Opportunity_ID")
    incoming = edited.set_index("Opportunity_ID")
    for column in SCORE_COLUMNS:
        current.loc[incoming.index, column] = pd.to_numeric(incoming[column], errors="coerce")
    if st.session_state.mode == "practice":
        fresh = apply_practice_scenario(load_csv("opportunity_data.csv")).set_index("Opportunity_ID")
        current["Evidence_Confidence"] = "Low"
        current["Score_Basis"] = "Practice assumption"
        for opportunity_id in incoming.index:
            changed = any(
                valid_score(current.at[opportunity_id, column])
                != valid_score(fresh.at[opportunity_id, column])
                for column in SCORE_COLUMNS
            )
            if changed:
                current.at[opportunity_id, "Assumptions_and_Data_Gaps"] = (
                    "Scores were edited in this session. They are still hypotheses, not recorded evidence."
                )
                current.at[opportunity_id, "Research_Notes"] = (
                    "Edited practice scenario. Not a market finding."
                )
    else:
        if "Evidence_Confidence" in incoming.columns:
            current.loc[incoming.index, "Evidence_Confidence"] = incoming["Evidence_Confidence"]
        current["Score_Basis"] = "Recorded evidence"
    st.session_state.table = current.reset_index()


def filter_table(frame: pd.DataFrame, products, cities, segments) -> pd.DataFrame:
    chosen = frame[
        frame["Product"].isin(products)
        & frame["City"].isin(cities)
        & frame["Customer_Segment"].isin(segments)
    ]
    return chosen.reset_index(drop=True)


def display_table(prepared: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Rank",
        "Decision_Status",
        "Opportunity_ID",
        "Product",
        "City",
        "Customer_Segment",
        "Likely_Channel",
        "Weighted_Opportunity_Score_0to100",
        "Evidence_Confidence",
        *SCORE_COLUMNS,
        "Score_Basis",
    ]
    show = prepared[columns].copy()
    show["Rank"] = show["Rank"].astype("Int64").astype(str).replace("<NA>", "—")
    return show


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; max-width: 1180px; }
        h1 { font-family: Georgia, "Times New Roman", serif; font-weight: 600;
             letter-spacing: -0.03em; margin-bottom: 0.2rem; }
        .eyebrow { letter-spacing: 0.14em; text-transform: uppercase;
                   font-size: 0.75rem; color: #6e655b; margin-bottom: 0.3rem; }
        .banner { border: 1px solid #e4c89a; background: #fff6e8;
                  border-radius: 12px; padding: 0.85rem 1rem; margin: 0.4rem 0 1rem; }
        .banner strong { color: #8a4b12; }
        .quiet { color: #5c564e; }
        div[data-testid="stMetric"] { background: #fffdf8; border: 1px solid #eadfce;
                                      border-radius: 12px; padding: 0.6rem 0.8rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls(table: pd.DataFrame):
    st.sidebar.header("Compare")
    mode_label = st.sidebar.radio(
        "Score source",
        ["Practice scenario", "Recorded evidence"],
        index=0 if st.session_state.mode == "practice" else 1,
        help=(
            "Practice scenario fills hypotheses so the ranking math can be checked. "
            "Recorded evidence uses only the scores saved in the dataset."
        ),
    )
    set_mode("practice" if mode_label == "Practice scenario" else "evidence")

    if st.sidebar.button("Reset scores to file"):
        reset_table()

    products = st.sidebar.multiselect(
        "Product", sorted(table["Product"].unique()), default=sorted(table["Product"].unique())
    )
    cities = st.sidebar.multiselect(
        "City", list(dict.fromkeys(table["City"])), default=list(dict.fromkeys(table["City"]))
    )
    segments = st.sidebar.multiselect(
        "Customer segment",
        list(dict.fromkeys(table["Customer_Segment"])),
        default=list(dict.fromkeys(table["Customer_Segment"])),
    )

    st.sidebar.header("Weights")
    st.sidebar.caption("From the scoring framework. They must add up to 100.")
    weights = {}
    defaults = dict(zip(CRITERION_NAMES, [30, 25, 20, 15, 10]))
    for name, default in defaults.items():
        weights[name] = int(
            st.sidebar.number_input(name, min_value=0, max_value=100, value=default, step=5)
        )
    criteria = criteria_from_weights(weights)
    valid_weights = weight_total(criteria) == 100
    if not valid_weights:
        st.sidebar.error(
            f"Weights add up to {weight_total(criteria)}. Change them until they add up to 100."
        )
    return products, cities, segments, criteria, valid_weights


def ranking_chart(prepared: pd.DataFrame):
    plot_source = prepared[prepared["Rankable"]].head(12).copy()
    if plot_source.empty:
        return None
    short_segment = {
        "Households / general consumers": "Households",
        "Students and young adults": "Students",
        "Health-conscious consumers": "Health-conscious",
        "Vegetarians, flexitarians and meat reducers": "Vegetarians",
    }
    short_product = {"Kafi soy yoghurt": "Kafi", "Tofu suya": "Tofu suya"}
    plot_source["Label"] = (
        plot_source["City"]
        + " · "
        + plot_source["Customer_Segment"].map(short_segment).fillna(plot_source["Customer_Segment"])
        + " · "
        + plot_source["Product"].map(short_product).fillna(plot_source["Product"])
    )
    figure = px.bar(
        plot_source.iloc[::-1],
        x="Weighted_Opportunity_Score_0to100",
        y="Label",
        color="Product",
        color_discrete_map=PRODUCT_COLORS,
        orientation="h",
        text="Weighted_Opportunity_Score_0to100",
        labels={
            "Weighted_Opportunity_Score_0to100": "Weighted score (0–100)",
            "Label": "",
        },
    )
    figure.update_traces(texttemplate="%{text:.0f}", textposition="outside", cliponaxis=False)
    figure.update_layout(
        height=520,
        margin=dict(l=8, r=40, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
        xaxis_range=[0, 100],
    )
    figure.update_yaxes(automargin=True)
    return figure


def contribution_chart(parts: list[dict]):
    usable = [part for part in parts if part["points"] is not None]
    if not usable:
        return None
    frame = pd.DataFrame(usable)
    figure = px.bar(
        frame,
        x="points",
        y="criterion",
        orientation="h",
        text="score",
        labels={"points": "Points toward the 0–100 score", "criterion": ""},
    )
    figure.update_traces(marker_color="#1f6b4a", texttemplate="score %{text}")
    figure.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(categoryorder="total ascending"),
    )
    return figure


def render_why(prepared: pd.DataFrame) -> None:
    rankable = prepared[prepared["Rankable"]]
    options = rankable if not rankable.empty else prepared
    if options.empty:
        st.info("No rows match these filters.")
        return
    labels = [
        f"{row.Opportunity_ID} · {row.City} · {row.Product} · {row.Customer_Segment}"
        for row in options.itertuples(index=False)
    ]
    choice = st.selectbox("Opportunity", labels)
    picked_id = choice.split(" · ", 1)[0]
    row = options[options["Opportunity_ID"] == picked_id].iloc[0]
    explanation = explain_opportunity(row, prepared)
    st.subheader(explanation["headline"])
    for sentence in explanation["sentences"][1:]:
        st.write(sentence)
    chart = contribution_chart(explanation["parts"])
    if chart is not None:
        st.plotly_chart(chart, width="stretch")
    else:
        st.caption("Add all five scores to see how many points each criterion would contribute.")


def render_workshop(table: pd.DataFrame) -> None:
    st.subheader("Scoring workshop")
    if st.session_state.mode == "practice":
        st.markdown(
            "These scores are the practice hypotheses. You can change a number to see the rank move. "
            "Confidence stays **Low** in this mode, so the launch shortlist stays empty."
        )
    else:
        st.markdown(
            "Type a score from 1 to 5 only when that criterion has evidence. "
            "Leave it blank when it does not. Set confidence to **High** only for a row you would defend to a judge. "
            "This screen does not save back into `data/opportunity_data.csv`."
        )
    editor_columns = [
        "Opportunity_ID",
        "Product",
        "City",
        "Customer_Segment",
        *SCORE_COLUMNS,
    ]
    if st.session_state.mode == "evidence":
        editor_columns.append("Evidence_Confidence")
    source = table[editor_columns].copy()
    edited = st.data_editor(
        source,
        hide_index=True,
        width="stretch",
        disabled=["Opportunity_ID", "Product", "City", "Customer_Segment"],
        key=editor_key(),
        column_config={
            column: st.column_config.NumberColumn(column, min_value=1, max_value=5, step=1)
            for column in SCORE_COLUMNS
        },
    )
    if isinstance(edited, pd.DataFrame):
        apply_editor(edited.reset_index() if edited.index.name == "Opportunity_ID" else edited)


def render_model() -> None:
    framework = load_csv("scoring_framework.csv")
    st.subheader("How a market is evaluated")
    st.markdown(
        """
        The question this tool answers is: **where is tofu suya, and where is Kafi soy yoghurt, most likely to succeed commercially?**

        Five criteria, agreed in the scoring framework, make up the score. Each is scored from 1 to 5. The weighted total is:

        `sum of (score × weight) ÷ 5`

        A total is calculated only when all five scores are present and each is a whole number from 1 to 5. Evidence confidence is shown beside the score. **Low confidence cannot enter the launch shortlist**, even when the number is high.
        """
    )
    st.dataframe(framework, hide_index=True, width="stretch")
    st.markdown(
        """
        **What the practice scenario assumes**

        - Demand follows the customer segment only: 4 for vegetarians, flexitarians, meat reducers, and health-conscious consumers; 3 for students and young adults; 2 for general households. No survey has been scored.
        - Affordability is 3 everywhere, because no price comparison is in the file.
        - Channel access is 3 everywhere, because a channel is named and outlet counts are not.
        - Supply is 3 where a 2024 state soybean figure is on the sheet, and 2 for Lagos, where that figure is blank. State tonnes are not treated as city supply.
        - Market gap is 3 for both products, because beef suya and dairy yoghurt are known substitutes and a competitor scan is still missing.

        Cities do not separate on demand, price, or channel until those columns are filled with evidence.
        """
    )


def render_gaps() -> None:
    st.subheader("What is measured, what is assumed, what is missing")
    opportunities = load_csv("opportunity_data.csv")
    survey = load_csv("survey_responses.csv")
    sources = load_csv("source_log.csv")
    filled_scores = opportunities[SCORE_COLUMNS].notna().sum().sum()
    left, right = st.columns(2)
    left.metric("Recorded criterion scores", int(filled_scores))
    right.metric("Survey responses", int(len(survey)))
    st.markdown(
        """
        The city and segment grid, the likely channel, and the 2024 state soybean figures are recorded. The soybean figures are state context from NAERLS, not proof that a city can supply a manufacturer.

        Prices, outlet counts, supplier quotes, survey answers, and the five scores are still empty in the file. The practice scenario does not fill that file.
        """
    )
    st.markdown("**Sources Amina logged**")
    st.dataframe(sources, hide_index=True, width="stretch")


def render_supply() -> None:
    st.subheader("State soybean context, 2024")
    cities = load_csv("city_context.csv")
    st.caption(cities["Interpretation / limitation"].iloc[0])
    plotted = cities.copy()
    plotted["Tonnes"] = pd.to_numeric(plotted["Soybean_Output_2024_tonnes"], errors="coerce")
    plotted["Shown"] = plotted["Tonnes"].fillna(0)
    plotted["Reported"] = plotted["Tonnes"].notna().map({True: "Figure recorded", False: "No figure in the sheet"})
    figure = px.bar(
        plotted,
        x="City",
        y="Shown",
        color="Reported",
        color_discrete_map={"Figure recorded": "#1f6b4a", "No figure in the sheet": "#c7bfb4"},
        labels={"Shown": "Soybean output (tonnes)", "City": ""},
    )
    figure.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    st.plotly_chart(figure, width="stretch")
    st.dataframe(
        cities[["City", "State/FCT", "Region", "Soybean_Output_2024_tonnes", "Source_ID"]],
        hide_index=True,
        width="stretch",
    )


def render_roles() -> None:
    st.subheader("Who does what")
    st.markdown(
        """
        **Muhammad — opportunity tool.** Build the tool, decide how a market is evaluated, score and rank segments and cities, show why each rank sits where it does, and test that a reader can follow the result. Deliverables: the scoring model, this prototype, and the ranked opportunities.

        **Amina — evidence.** Research the Nigerian tofu, soy, and meat market. Document customers who are reducing meat, health-conscious shoppers, vegetarians and flexitarians, and people looking for cheaper protein. Compare beef suya and other soy products. Record preferences and willingness to pay. Keep sources, and keep verified facts separate from assumptions. She owns the dataset.

        **Ibrahim — commercial case.** Decide where and how the product can make money. Compare suya spots and street vendors, restaurants, and supermarkets. Compare the cost of tofu suya with beef suya. Name the cities worth a closer look. Judge demand, affordability, competition, and distribution. Turn the ranked output into a business recommendation.
        """
    )


def main() -> None:
    st.set_page_config(
        page_title="Tofu suya and Kafi market opportunities",
        page_icon="🥣",
        layout="wide",
    )
    inject_css()
    init_state()

    st.markdown('<p class="eyebrow">Hack the Fork Nigeria 2026 · Challenge 3</p>', unsafe_allow_html=True)
    st.title("Where can tofu suya and Kafi soy yoghurt succeed?")
    st.markdown(
        '<p class="quiet">An explainable ranking for six Nigerian cities and four customer segments. '
        "The score is a weighted model, not a chatbot guess.</p>",
        unsafe_allow_html=True,
    )

    products, cities, segments, criteria, valid_weights = sidebar_controls(st.session_state.table)

    if st.session_state.mode == "practice":
        st.markdown(
            """
            <div class="banner">
            <strong>Practice scenario.</strong>
            The scores below are hypotheses so the ranking can be checked.
            They are not survey results, prices, or supplier quotes.
            The launch shortlist stays empty while confidence is Low.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="banner">
            <strong>Recorded evidence only.</strong>
            A row is ranked when all five scores are in the table.
            Blank cells stay blank. Nothing on this screen is written back to the dataset file.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not valid_weights:
        st.error("The ranking is paused until the five weights add up to 100.")
        render_model()
        return

    # The workshop returns edited scores. It has to run before the rank is
    # drawn. Placeholders keep the numbers visually above the tabs.
    metric_slot = st.empty()
    summary_slot = st.empty()
    ranking_tab, why_tab, workshop_tab, model_tab, gaps_tab, supply_tab, roles_tab = st.tabs(
        [
            "Ranking",
            "Why this rank",
            "Scoring workshop",
            "Scoring model",
            "Evidence and gaps",
            "Soybean context",
            "Team roles",
        ]
    )

    with workshop_tab:
        render_workshop(st.session_state.table)

    filtered = filter_table(st.session_state.table, products, cities, segments)
    prepared = ranked_view(prepare_opportunities(filtered, criteria))
    launch_count = int((prepared["Decision_Status"] == "Shortlist").sum())
    rankable_count = int(prepared["Rankable"].sum())
    top_score = prepared.loc[prepared["Rankable"], "Weighted_Opportunity_Score_0to100"].max()
    top_label = f"{top_score:.1f}" if pd.notna(top_score) else "—"

    with metric_slot.container():
        metric_cols = st.columns(4)
        metric_cols[0].metric("In this filter", len(prepared))
        metric_cols[1].metric("Rankable", rankable_count)
        metric_cols[2].metric("Top score", top_label)
        metric_cols[3].metric("Shortlist", launch_count)
    summary_slot.write(result_summary(prepared))

    with ranking_tab:
        chart = ranking_chart(prepared)
        if chart is None:
            st.info(
                "No rankable rows in this filter. Open the scoring workshop to enter five scores, "
                "or switch the sidebar to the practice scenario."
            )
        else:
            st.plotly_chart(chart, width="stretch")
            st.caption("Top 12 rankable rows in this filter. Shared scores are real ties.")
        st.dataframe(display_table(prepared), hide_index=True, width="stretch")
        st.download_button(
            "Download this ranking as CSV",
            data=display_table(prepared).to_csv(index=False).encode("utf-8"),
            file_name="ranked_opportunities.csv",
            mime="text/csv",
        )

    with why_tab:
        render_why(prepared)

    with model_tab:
        render_model()

    with gaps_tab:
        render_gaps()

    with supply_tab:
        render_supply()

    with roles_tab:
        render_roles()


main()
