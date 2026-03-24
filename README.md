# PHASE 1
Yes. Here is the logic, end to end.

# 1. What the current system is actually doing

Your current POC does **not** use a trained fraud model yet.
Right now it uses:

* **synthetic claim patterns**
* **derived features**
* **deterministic rules**
* **a cumulative rule score**
* **a risk band**
* **an LLM explanation layer for flagged claims**

So the fraud/anomaly detection logic is currently **rule-based scoring**, not statistical anomaly detection.

---

# 2. The main idea

We are trying to identify claims that look suspicious because they contain one or more of these patterns:

* claim filed very soon after policy start
* unusually high repair estimate
* repeated claimant/contact/repair-shop linkage
* multiple recent prior claims
* inconsistency between claimant narrative and adjuster note
* suspicious wording in the adjuster note

Each suspicious pattern adds points.
More points = more suspicious.

---

# 3. Features we derive before scoring

From the raw claim fields, we compute a few useful signals.

## A. `days_since_policy_start`

Calculated as:

```python
incident_date - policy_start_date
```

Interpretation:

* very small value = suspicious
* example: claim 5 days after policy start

Why it matters:

* early claims are a classic fraud indicator

---

## B. `reporting_delay_days`

Calculated as:

```python
claim_report_date - incident_date
```

Interpretation:

* long delay may be suspicious
* not always fraud, but worth scoring lightly

---

## C. `repair_cost_band`

We bucket the repair cost into:

* low
* medium
* high
* very_high

This is mostly for readability and UI support, though the actual rules use the numeric amount.

---

## D. `adjuster_suspicious_keyword_hits`

We scan the adjuster note for phrases like:

* inconsistent
* does not match
* unusually high
* elevated
* linked
* flagged
* limited visible damage
* shortly after policy

Interpretation:

* if the adjuster note already contains suspicious language, we increase the score

---

# 4. Rules used to calculate the fraud score

Each rule adds points to a `rule_score`.

## Rule 1 — Early policy claim

Condition:

```python
days_since_policy_start < 15
```

Score added:

```python
+3
```

Reason:
A claim very soon after policy start is a strong suspicious signal.

Rule hit recorded as:

* `"claim filed shortly after policy start"`

---

## Rule 2 — Delayed reporting

Condition:

```python
reporting_delay_days > 7
```

Score added:

```python
+1
```

Reason:
Delayed reporting can be suspicious, but by itself it is weak.

Rule hit:

* `"claim reported with unusual delay"`

---

## Rule 3 — High repair estimate

Condition:

```python
estimated_repair_cost > 8000
```

Score added:

```python
+2
```

Reason:
A high repair cost can indicate inflation or exaggerated damage.

Rule hit:

* `"repair estimate above normal threshold"`

---

## Rule 4 — Very high repair estimate

Condition:

```python
estimated_repair_cost > 12000
```

Score added:

```python
+1
```

Reason:
Extremely high estimates deserve extra scrutiny.

Rule hit:

* `"repair estimate exceptionally high"`

This is additive with Rule 3.

---

## Rule 5 — Multiple prior claims

Condition:

```python
prior_claims_12m >= 2
```

Score added:

```python
+2
```

Reason:
Frequent claims in a short period can indicate abnormal behavior.

Rule hit:

* `"multiple prior claims in the last 12 months"`

---

## Rule 6 — Same phone linked to multiple claims

Condition:

```python
linked_claims_same_phone >= 2
```

Score added:

```python
+2
```

Reason:
Repeated contact details across claims can indicate organized or recycled claims.

Rule hit:

* `"same phone number linked to multiple claims"`

---

## Rule 7 — Same repair shop linked to multiple claims

Condition:

```python
linked_claims_same_repair_shop >= 5
```

Score added:

```python
+2
```

Reason:
Repeated concentration around the same repair shop may indicate suspicious clustering.

Rule hit:

* `"repair shop linked to multiple claims"`

---

## Rule 8 — Suspicious wording in adjuster note

Condition:

```python
adjuster_suspicious_keyword_hits >= 1
```

Score added:

```python
+2
```

Reason:
If the adjuster already uses suspicious language, that is a meaningful signal.

Rule hit:

* `"adjuster note contains suspicious language"`

---

## Rule 9 — Explicit inconsistency in narrative vs damage

Condition:
If adjuster note contains phrases like:

* `"inconsistent"`
* `"does not match"`

Score added:

```python
+3
```

Reason:
This is one of the strongest fraud indicators in the current POC.

Rule hit:

* `"narrative inconsistency detected"`

---

## Rule 10 — Theft claim with very short narrative

Condition:

```python
claim_type == "theft" and len(claimant_narrative) < 60
```

Score added:

```python
+1
```

Reason:
A vague theft narrative can be a weak suspicious signal.

Rule hit:

* `"brief theft narrative with limited detail"`

---

## Rule 11 — Single-area damage with unusually high cost

Condition:

```python
damage_area in {"front", "rear", "left side", "right side"} and estimated_repair_cost > 10000
```

Score added:

```python
+1
```

Reason:
Limited damage scope combined with very high cost may suggest estimate inflation.

Rule hit:

* `"single-area damage with unusually high repair cost"`

---

# 5. How the total score is calculated

The system simply adds all triggered rule weights.

Example:

* early policy claim: `+3`
* high repair estimate: `+2`
* same phone repeated: `+2`
* suspicious adjuster wording: `+2`

Total:

```text
rule_score = 9
```

So the score is a **weighted sum of suspicious indicators**.

---

# 6. How risk levels are assigned

After calculating `rule_score`, we map it to a risk band.

## Current mapping

### Low risk

```python
score <= 2
```

### Medium risk

```python
3 <= score <= 5
```

### High risk

```python
score >= 6
```

This is intentionally simple for the POC.

---

# 7. How decisions are assigned

From the risk band, the pipeline assigns a review action.

## Low risk

```text
approve_or_fast_track
```

Meaning:

* no major suspicion
* can move faster through the workflow

## Medium risk

```text
review_with_slm
```

Meaning:

* suspicious enough for AI-assisted review
* send to LLM for summary and analysis

## High risk

```text
priority_investigation
```

Meaning:

* significant suspicious indicators
* prioritize investigator review

---

# 8. Where “anomaly detection” fits today

Strictly speaking, your current version is **not yet true anomaly detection**.

It is:

* **rule-based fraud scoring**
* with some heuristic abnormality signals

True anomaly detection would involve a model such as:

* Isolation Forest
* One-Class SVM
* Autoencoder
* clustering-based outlier detection

That would identify claims that are statistically unusual compared with the rest of the population.

We have not added that yet.

---

# 9. What the LLM does vs what the score does

This distinction is very important.

## The score decides:

* how suspicious the claim is
* whether it should be escalated

## The LLM does not decide fraud

The LLM:

* summarizes the claim
* identifies inconsistencies
* extracts evidence
* generates an investigator note
* suggests review priority in natural language

So:

* **rules/score = primary detection**
* **LLM = explanation and triage support**

That is the right architecture.

---

# 10. Example of the scoring logic in practice

Take this claim:

* `days_since_policy_start = 6`
* `estimated_repair_cost = 11800`
* `prior_claims_12m = 3`
* `linked_claims_same_phone = 4`
* `linked_claims_same_repair_shop = 7`
* adjuster note says estimate is elevated

Triggered rules:

* early policy claim → `+3`
* high repair estimate → `+2`
* multiple prior claims → `+2`
* same phone repeated → `+2`
* same repair shop repeated → `+2`
* suspicious adjuster wording → `+2`
* single-area damage with high cost → `+1`

Total:

```text
rule_score = 14
```

Risk band:

```text
high
```

Decision:

```text
priority_investigation
```

Then the LLM explains *why*.

---

# 11. Why this works for a POC

This approach is good for a POC because it is:

* easy to understand
* easy to debug
* easy to explain to business users
* easy to tune
* easy to connect to synthetic data
* compatible with later ML upgrades

It also gives you traceability:
for every suspicious claim, you can say exactly which rules fired.

That is very valuable.

---

# 12. Limitations of the current scoring logic

This is important to be honest about.

## It is heuristic

The thresholds are hand-crafted, not learned from real outcomes.

## It is additive

It assumes the total suspicion is just the sum of rule weights.

## It is not calibrated

A score of 8 does not yet mean “80% fraud probability.”

## It may double count related signals

For example:

* high repair cost
* very high repair cost
* suspicious note about estimate

These can reinforce each other, but they are partially correlated.

## It does not yet learn from outcomes

No feedback loop yet:

* confirmed fraud
* false positives
* investigator decisions

---

# 13. How we would improve this later

The natural evolution is:

## Phase 1 — current state

Weighted rules

## Phase 2

Add anomaly detection:

* Isolation Forest on numeric features

## Phase 3

Add supervised model:

* logistic regression
* XGBoost

## Phase 4

Calibrate score and threshold using real claims outcomes

## Phase 5

Use graph/link analytics for repeated entities and fraud rings

---

# 14. Clean summary in one sentence

Your current POC identifies suspicious auto claims by **deriving a few fraud-relevant features, applying weighted business rules, summing the triggered rule weights into a risk score, mapping that score to low/medium/high risk, and then using the LLM to explain and summarize flagged claims**.

If you want, the next thing I can do is turn this into a **one-page architecture/design note** you can reuse in your project documentation.
