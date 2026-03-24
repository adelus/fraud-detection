from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


@dataclass
class AnomalyDetectionResult:
    dataframe: pd.DataFrame
    feature_columns: List[str]


class ClaimAnomalyDetector:
    """
    Isolation Forest wrapper for claim anomaly detection.

    Notes:
    - This detects unusual claims, not confirmed fraud.
    - We fit on the available dataset and score the same dataset for the POC.
    - In a more mature version, fit/train and scoring would be separated.
    """

    def __init__(
        self,
        contamination: float = 0.12,
        random_state: int = 42
    ) -> None:
        self.contamination = contamination
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=200,
            contamination=self.contamination,
            random_state=self.random_state,
        )

    @staticmethod
    def get_feature_columns() -> List[str]:
        return [
            "days_since_policy_start",
            "reporting_delay_days",
            "estimated_repair_cost",
            "prior_claims_12m",
            "linked_claims_same_phone",
            "linked_claims_same_repair_shop",
        ]

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        feature_columns = self.get_feature_columns()

        missing = [col for col in feature_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required anomaly feature columns: {missing}")

        x = df[feature_columns].copy()

        # Basic imputation for POC robustness
        x = x.fillna(0)

        return x

    def fit_score(self, df: pd.DataFrame) -> AnomalyDetectionResult:
        feature_columns = self.get_feature_columns()
        x = self.prepare_features(df)

        x_scaled = self.scaler.fit_transform(x)

        # predict: 1 = normal, -1 = anomaly
        anomaly_prediction = self.model.fit_predict(x_scaled)

        # decision_function:
        # higher = more normal, lower = more anomalous
        decision_scores = self.model.decision_function(x_scaled)

        scored_df = df.copy()
        scored_df["anomaly_prediction"] = anomaly_prediction
        scored_df["anomaly_decision_score"] = decision_scores

        # Convert so that HIGHER means MORE anomalous
        scored_df["anomaly_score_raw"] = -1 * scored_df["anomaly_decision_score"]

        # Normalize anomaly score to 0..100 for easier combination with rule score
        min_score = scored_df["anomaly_score_raw"].min()
        max_score = scored_df["anomaly_score_raw"].max()

        if max_score == min_score:
            scored_df["anomaly_score_normalized"] = 0.0
        else:
            scored_df["anomaly_score_normalized"] = (
                (scored_df["anomaly_score_raw"] - min_score) / (max_score - min_score)
            ) * 100.0

        return AnomalyDetectionResult(
            dataframe=scored_df,
            feature_columns=feature_columns
        )