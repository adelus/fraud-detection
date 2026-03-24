# Auto Claims Fraud Detection (POC)

This project demonstrates a hybrid fraud detection system for auto insurance claims.

The goal is not only to detect suspicious claims, but to make decisions explainable and actionable for investigators.

The system combines:

- Rule-based scoring (known fraud patterns)
- Anomaly detection (Isolation Forest)
- LLM-based explanations (investigator support)

Live demo: [Add your Streamlit link here]

---

## Architecture

The system follows a hybrid fraud detection approach:

Claims Data  
→ Feature Engineering  
→ Rule-Based Scoring  
→ Anomaly Detection (Isolation Forest)  
→ Combined Risk Score  
→ LLM Explanation Layer  
→ Investigator UI (Streamlit)

---

## Key Concepts

- **Rules** capture known fraud patterns  
  (e.g. early claims, repeated entities, inconsistent narratives)

- **Anomaly detection** identifies claims that deviate from normal behavior

- **Hybrid scoring** combines both approaches into a final risk score

- **LLM is used for explanation, not detection**  
  → generates summaries, inconsistencies, and investigator notes

---

## Detection Logic (Detailed)

### 1. What the system is doing

This POC does not rely on a trained fraud model yet.

It uses:

- synthetic claim patterns  
- derived features  
- deterministic rules  
- a cumulative rule score  
- a risk classification  
- an LLM explanation layer  

The fraud detection logic is primarily **rule-based scoring**, enhanced with anomaly detection.

---

### 2. Main idea

Claims are flagged as suspicious when they exhibit patterns such as:

- claim filed shortly after policy start  
- unusually high repair estimate  
- repeated claimant / phone / repair shop  
- multiple recent prior claims  
- inconsistency between narrative and adjuster note  
- suspicious wording in adjuster notes  

Each signal contributes to a cumulative score.

---

### 3. Derived features

#### days_since_policy_start
incident_date - policy_start_date

- low values are suspicious

#### reporting_delay_days

claim_report_date - incident_date

- long delays may indicate risk

#### repair_cost_band
Categorized into:
- low / medium / high / very_high

#### adjuster_suspicious_keyword_hits
Detects keywords like:
- inconsistent
- does not match
- unusually high
- limited damage

---

### 4. Rule-based scoring

Each triggered rule adds points.

Examples:

| Rule | Condition | Score |
|------|----------|------|
| Early claim | < 15 days | +3 |
| High repair cost | > 8000 | +2 |
| Very high cost | > 12000 | +1 |
| Multiple prior claims | ≥ 2 | +2 |
| Same phone reuse | ≥ 2 | +2 |
| Repair shop reuse | ≥ 5 | +2 |
| Suspicious adjuster note | keywords | +2 |
| Narrative inconsistency | mismatch | +3 |

Final rule score = sum of triggered rules

---

### 5. Anomaly detection

Isolation Forest is used to detect unusual claims.

It analyzes features such as:
- repair cost
- claim timing
- prior claims
- linked entities

Output:
- anomaly score (normalized)
- higher = more unusual

---

### 6. Hybrid scoring

Final score combines:


final_score =
0.60 * rule_score_normalized +
0.40 * anomaly_score_normalized


Why:
- rules = explainable
- anomaly detection = captures unknown patterns

---

### 7. Risk classification

| Score | Risk |
|------|------|
| < 30 | Low |
| 30–60 | Medium |
| > 60 | High |

---

### 8. Decision logic

| Risk | Action |
|------|--------|
| Low | Approve / fast track |
| Medium | LLM-assisted review |
| High | Priority investigation |

---

### 9. Role of the LLM

The LLM does NOT detect fraud.

It is used to:

- summarize claims  
- highlight inconsistencies  
- extract evidence  
- generate investigator notes  

This improves explainability and analyst efficiency

---

## Limitations

- Rule thresholds are heuristic (not learned)
- Anomaly detection identifies unusual behavior, not confirmed fraud
- Scores are not calibrated probabilities
- Some signals may be correlated (double counting)
- No feedback loop from investigators yet

---

## Future Improvements

- Add supervised ML model (logistic regression / XGBoost)
- Introduce RAG with fraud policies and case history
- Implement feedback loop from investigators
- Add graph-based fraud detection (entity linking)
- Improve score calibration and threshold tuning

---

## Project Structure


streamlit_app.py → UI (deployed demo)
fraud_scoring_pipeline.py → rule-based scoring
anomaly_detector.py → anomaly detection (Isolation Forest)
slm_case_enrichment.py → LLM explanation layer
enriched_claims.jsonl → precomputed demo data

---

## Deployment

The deployed version uses **precomputed LLM outputs** for simplicity and stability.

In a production setup:
- the UI would call a remote model service
- scoring and inference would run in backend services

---

## Key Insight

Fraud detection systems should not rely on a single technique.

The most effective approach combines:

- deterministic rules  
- statistical anomaly detection  
- human-in-the-loop decision making  
- AI-assisted explanations  

---

## About this project

This project was built to explore how  AI techniques can support fraud detection systems in a practical, explainable way.

Happy to discuss with others working on:
- fraud detection
- risk systems
- AI applications in enterprise systems