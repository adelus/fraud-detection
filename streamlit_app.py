import json
from pathlib import Path

import pandas as pd
import streamlit as st

INPUT_FILE = "enriched_claims.jsonl"


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    records = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            obj = json.loads(line)
            claim = obj.get("claim", {})
            llm_output = obj.get("llm_output", {})

            records.append({
                "claim_id": claim.get("claim_id"),
                "policy_id": claim.get("policy_id"),
                "claim_type": claim.get("claim_type"),
                "damage_area": claim.get("damage_area"),
                "estimated_repair_cost": claim.get("estimated_repair_cost"),
                "incident_city": claim.get("incident_city"),
                "days_since_policy_start": claim.get("days_since_policy_start"),
                "reporting_delay_days": claim.get("reporting_delay_days"),
                "prior_claims_12m": claim.get("prior_claims_12m"),
                "linked_claims_same_phone": claim.get("linked_claims_same_phone"),
                "linked_claims_same_repair_shop": claim.get("linked_claims_same_repair_shop"),

                # Scores (NEW)
                "rule_score": claim.get("rule_score"),
                "rule_score_normalized": claim.get("rule_score_normalized"),
                "anomaly_score_normalized": claim.get("anomaly_score_normalized"),
                "final_score": claim.get("final_score"),
                "risk_level": claim.get("risk_level"),
                "rules_triggered": claim.get("rules_triggered", []),

                # Text
                "claimant_narrative": claim.get("claimant_narrative"),
                "adjuster_note": claim.get("adjuster_note"),

                # LLM
                "summary": llm_output.get("summary", ""),
                "inconsistencies": llm_output.get("inconsistencies", []),
                "risk_factors": llm_output.get("risk_factors", []),
                "evidence": llm_output.get("evidence", []),
                "recommended_review_priority": llm_output.get("recommended_review_priority", ""),
                "investigator_note": llm_output.get("investigator_note", ""),
            })

    return pd.DataFrame(records)


def render_list(items):
    if not items:
        st.write("None")
        return
    for item in items:
        st.markdown(f"- {item}")


def main():
    st.set_page_config(page_title="Fraud Detection POC", layout="wide")

    st.title("🚗 Auto Claims Fraud Detection POC")
    st.caption("Hybrid System: Rules + Anomaly Detection + LLM Explanation")

    if not Path(INPUT_FILE).exists():
        st.error("Run slm_case_enrichment.py first.")
        return

    df = load_data(INPUT_FILE)

    if df.empty:
        st.warning("No data found.")
        return

    # --- FILTERS ---
    st.sidebar.header("Filters")

    risk_filter = st.sidebar.multiselect(
        "Risk level",
        options=df["risk_level"].dropna().unique(),
        default=df["risk_level"].dropna().unique(),
    )

    df = df[df["risk_level"].isin(risk_filter)]

    # --- TOP METRICS ---
    st.subheader("📊 Portfolio Overview")
    #st.bar_chart(df["risk_level"].value_counts())
    st.markdown("### Risk Distribution")
    st.bar_chart(df["risk_level"].value_counts())
    #st.markdown("### Score Distribution")
    #st.bar_chart(df[["rule_score", "anomaly_score_normalized", "final_score"]])

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Claims", len(df))
    col2.metric("High Risk", int((df["risk_level"] == "high").sum()))
    col3.metric("Medium Risk", int((df["risk_level"] == "medium").sum()))
    col4.metric("Low Risk", int((df["risk_level"] == "low").sum()))

    st.markdown("### Score Distribution")

    colA, colB, colC = st.columns(3)
    colA.metric("Avg Rule Score", f"{df['rule_score'].mean():.2f}")
    colB.metric("Avg Anomaly Score", f"{df['anomaly_score_normalized'].mean():.2f}")
    colC.metric("Avg Final Score", f"{df['final_score'].mean():.2f}")

    # --- TABLE ---
    st.subheader("📋 Claims Table")

    st.dataframe(
        df[[
            "claim_id",
            "incident_city",
            "estimated_repair_cost",
            "rule_score",
            "anomaly_score_normalized",
            "final_score",
            "risk_level"
        ]].sort_values(by="final_score", ascending=False),
        use_container_width=True
    )

    # --- CLAIM DETAIL ---
    st.subheader("🔍 Claim Review")

    selected_id = st.selectbox("Select Claim", df["claim_id"])

    row = df[df["claim_id"] == selected_id].iloc[0]

    # --- SCORES ---
    st.markdown("## 🎯 Scoring Breakdown")

    c1, c2, c3 = st.columns(3)

    c1.metric("Rule Score", f"{row['rule_score']}")
    #c2.metric("Anomaly Score", f"{row['anomaly_score_normalized']:.2f}")
    anomaly_score = row.get("anomaly_score_normalized")
    if anomaly_score is None or pd.isna(anomaly_score):
        c2.metric("Anomaly Score", "N/A")
    else:
        c2.metric("Anomaly Score", f"{anomaly_score:.2f}")
    #c3.metric("Final Score", f"{row['final_score']:.2f}")
    final_score = row.get("final_score")
    if final_score is None or pd.isna(final_score):
        c3.metric("Final Score", "N/A")
    else:
        c3.metric("Final Score", f"{final_score:.2f}")

    st.markdown(f"**Risk Level:** `{row['risk_level']}`")

    # --- WHY FLAGGED ---
    st.markdown("## ⚠️ Why was this claim flagged?")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Rules Triggered")
        render_list(row["rules_triggered"])

    with col2:
        st.markdown("### Anomaly Insight")
        st.write(
            "This claim deviates from normal patterns based on numerical features "
            "(cost, timing, linked entities)."
        )

    # --- TEXT ---
    st.markdown("## 📝 Claim Details")

    st.markdown("### Claimant Narrative")
    st.info(row["claimant_narrative"])

    st.markdown("### Adjuster Note")
    st.warning(row["adjuster_note"])

    # --- LLM OUTPUT ---
    st.markdown("## 🤖 LLM Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Summary")
        st.success(row["summary"])

        st.markdown("### Investigator Note")
        st.write(row["investigator_note"])

    with col2:
        st.markdown("### Inconsistencies")
        render_list(row["inconsistencies"])

        st.markdown("### Risk Factors")
        render_list(row["risk_factors"])

        st.markdown("### Evidence")
        render_list(row["evidence"])

    # --- RAW JSON ---
    with st.expander("Raw Data"):
        st.json(row.to_dict())


if __name__ == "__main__":
    main()