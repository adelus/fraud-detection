import json
from pathlib import Path

import pandas as pd

from anomaly_detector import ClaimAnomalyDetector


INPUT_CSV = "synthetic_auto_claims.csv"
OUTPUT_SCORED_CSV = "scored_auto_claims.csv"
OUTPUT_FLAGGED_CSV = "flagged_auto_claims.csv"
OUTPUT_SLM_JSONL = "flagged_claims_for_slm.jsonl"


def load_claims(input_csv: str) -> pd.DataFrame:
    return pd.read_csv(input_csv)


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    date_cols = ["policy_start_date", "incident_date", "claim_report_date"]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")

    df["days_since_policy_start"] = (
        df["incident_date"] - df["policy_start_date"]
    ).dt.days

    df["reporting_delay_days"] = (
        df["claim_report_date"] - df["incident_date"]
    ).dt.days

    df["repair_cost_band"] = pd.cut(
        df["estimated_repair_cost"],
        bins=[-1, 2500, 5000, 8000, 20000],
        labels=["low", "medium", "high", "very_high"],
    )

    df["claimant_narrative"] = df["claimant_narrative"].fillna("")
    df["adjuster_note"] = df["adjuster_note"].fillna("")

    suspicious_keywords = [
        "inconsistent",
        "does not match",
        "unusually high",
        "elevated",
        "linked",
        "flagged",
        "limited visible damage",
        "shortly after policy",
    ]

    def keyword_hit_count(text: str) -> int:
        t = text.lower()
        return sum(1 for kw in suspicious_keywords if kw in t)

    df["adjuster_suspicious_keyword_hits"] = df["adjuster_note"].apply(keyword_hit_count)

    return df


def evaluate_rules(row: pd.Series) -> tuple[int, list[str]]:
    score = 0
    hits = []

    days_since_policy_start = row.get("days_since_policy_start", 9999)
    reporting_delay_days = row.get("reporting_delay_days", 0)
    repair_cost = row.get("estimated_repair_cost", 0)
    prior_claims = row.get("prior_claims_12m", 0)
    linked_same_phone = row.get("linked_claims_same_phone", 0)
    linked_same_shop = row.get("linked_claims_same_repair_shop", 0)
    keyword_hits = row.get("adjuster_suspicious_keyword_hits", 0)
    note_text = str(row.get("adjuster_note", "")).lower()
    damage_area = str(row.get("damage_area", "")).lower()
    claim_type = str(row.get("claim_type", "")).lower()

    if pd.notna(days_since_policy_start) and days_since_policy_start < 15:
        score += 3
        hits.append("claim filed shortly after policy start")

    if pd.notna(reporting_delay_days) and reporting_delay_days > 7:
        score += 1
        hits.append("claim reported with unusual delay")

    if repair_cost > 8000:
        score += 2
        hits.append("repair estimate above normal threshold")

    if repair_cost > 12000:
        score += 1
        hits.append("repair estimate exceptionally high")

    if prior_claims >= 2:
        score += 2
        hits.append("multiple prior claims in the last 12 months")

    if linked_same_phone >= 2:
        score += 2
        hits.append("same phone number linked to multiple claims")

    if linked_same_shop >= 5:
        score += 2
        hits.append("repair shop linked to multiple claims")

    if keyword_hits >= 1:
        score += 2
        hits.append("adjuster note contains suspicious language")

    if "inconsistent" in note_text or "does not match" in note_text:
        score += 3
        hits.append("narrative inconsistency detected")

    if claim_type == "theft" and len(str(row.get("claimant_narrative", ""))) < 60:
        score += 1
        hits.append("brief theft narrative with limited detail")

    if damage_area in {"front", "rear", "left side", "right side"} and repair_cost > 10000:
        score += 1
        hits.append("single-area damage with unusually high repair cost")

    return score, hits


def add_rule_scores(df: pd.DataFrame) -> pd.DataFrame:
    rule_scores = []
    rule_hits_list = []

    for _, row in df.iterrows():
        rule_score, rule_hits = evaluate_rules(row)
        rule_scores.append(rule_score)
        rule_hits_list.append(rule_hits)

    df = df.copy()
    df["rule_score"] = rule_scores
    df["rule_hits"] = rule_hits_list
    return df


def normalize_rule_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    max_rule_score = df["rule_score"].max()

    if max_rule_score == 0:
        df["rule_score_normalized"] = 0.0
    else:
        df["rule_score_normalized"] = (df["rule_score"] / max_rule_score) * 100.0

    return df


def combine_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weighted hybrid score:
    - Rules capture known suspicious patterns
    - Isolation Forest captures unusual combinations

    We give a bit more weight to rules because they are explainable and intentional.
    """
    df = df.copy()

    df["final_score"] = (
        0.60 * df["rule_score_normalized"] +
        0.40 * df["anomaly_score_normalized"]
    )

    return df


def assign_risk_level_from_final_score(final_score: float) -> str:
    if final_score < 30:
        return "low"
    if final_score < 60:
        return "medium"
    return "high"


def assign_review_decision(risk: str) -> str:
    if risk == "low":
        return "approve_or_fast_track"
    if risk == "medium":
        return "review_with_slm"
    return "priority_investigation"


def classify_claims(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["risk_level"] = df["final_score"].apply(assign_risk_level_from_final_score)
    df["review_decision"] = df["risk_level"].apply(assign_review_decision)
    return df


def build_slm_payload(row: pd.Series) -> dict:
    return {
        "claim_id": row["claim_id"],
        "policy_id": row["policy_id"],
        "claim_type": row["claim_type"],
        "damage_area": row["damage_area"],
        "estimated_repair_cost": float(row["estimated_repair_cost"]),
        "incident_city": row["incident_city"],
        "days_since_policy_start": int(row["days_since_policy_start"])
        if pd.notna(row["days_since_policy_start"])
        else None,
        "reporting_delay_days": int(row["reporting_delay_days"])
        if pd.notna(row["reporting_delay_days"])
        else None,
        "prior_claims_12m": int(row["prior_claims_12m"]),
        "linked_claims_same_phone": int(row["linked_claims_same_phone"]),
        "linked_claims_same_repair_shop": int(row["linked_claims_same_repair_shop"]),
        "claimant_narrative": row["claimant_narrative"],
        "adjuster_note": row["adjuster_note"],
        "rule_score": float(row["rule_score"]),
        "rule_score_normalized": float(row["rule_score_normalized"]),
        "anomaly_score_normalized": float(row["anomaly_score_normalized"]),
        "final_score": float(row["final_score"]),
        "risk_level": row["risk_level"],
        "rules_triggered": row["rule_hits"],
    }


def export_outputs(df: pd.DataFrame) -> None:
    export_df = df.copy()
    export_df["rule_hits"] = export_df["rule_hits"].apply(json.dumps)
    export_df.to_csv(OUTPUT_SCORED_CSV, index=False)

    flagged_df = df[df["risk_level"].isin(["medium", "high"])].copy()
    flagged_export_df = flagged_df.copy()
    flagged_export_df["rule_hits"] = flagged_export_df["rule_hits"].apply(json.dumps)
    flagged_export_df.to_csv(OUTPUT_FLAGGED_CSV, index=False)

    with open(OUTPUT_SLM_JSONL, "w", encoding="utf-8") as f:
        for _, row in flagged_df.iterrows():
            payload = build_slm_payload(row)
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def print_summary(df: pd.DataFrame) -> None:
    total = len(df)
    low_count = int((df["risk_level"] == "low").sum())
    medium_count = int((df["risk_level"] == "medium").sum())
    high_count = int((df["risk_level"] == "high").sum())

    print("\n=== Hybrid Fraud Scoring Summary ===")
    print(f"Total claims: {total}")
    print(f"Low risk:     {low_count}")
    print(f"Medium risk:  {medium_count}")
    print(f"High risk:    {high_count}")

    print("\n=== Risk Level by Fraud Pattern ===")
    summary = (
        df.groupby(["fraud_pattern_type", "risk_level"])
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )
    print(summary)

    print("\n=== Sample Flagged Claims ===")
    flagged = df[df["risk_level"].isin(["medium", "high"])][
        [
            "claim_id",
            "fraud_pattern_type",
            "rule_score",
            "anomaly_score_normalized",
            "final_score",
            "risk_level",
            "rule_hits",
        ]
    ].head(10)

    for _, row in flagged.iterrows():
        print(
            f"- {row['claim_id']} | pattern={row['fraud_pattern_type']} "
            f"| rule_score={row['rule_score']}"
            f" | anomaly={row['anomaly_score_normalized']:.2f}"
            f" | final_score={row['final_score']:.2f}"
            f" | risk={row['risk_level']}"
        )
        print(f"  rules: {row['rule_hits']}")


def main() -> None:
    if not Path(INPUT_CSV).exists():
        raise FileNotFoundError(
            f"Input file '{INPUT_CSV}' not found. Generate it first with synthetic_data_generator.py."
        )

    df = load_claims(INPUT_CSV)
    df = derive_features(df)
    df = add_rule_scores(df)
    df = normalize_rule_score(df)

    anomaly_detector = ClaimAnomalyDetector(
        contamination=0.12,
        random_state=42
    )
    anomaly_result = anomaly_detector.fit_score(df)
    df = anomaly_result.dataframe

    df = combine_scores(df)
    df = classify_claims(df)

    export_outputs(df)
    print_summary(df)

    print("\nGenerated files:")
    print(f"- {OUTPUT_SCORED_CSV}")
    print(f"- {OUTPUT_FLAGGED_CSV}")
    print(f"- {OUTPUT_SLM_JSONL}")


if __name__ == "__main__":
    main()