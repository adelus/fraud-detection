import json
import re
from pathlib import Path

import requests
from tqdm import tqdm

INPUT_FILE = "flagged_claims_for_slm.jsonl"
OUTPUT_FILE = "enriched_claims.jsonl"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"


def build_prompt(claim_json: dict) -> str:
    return f"""
You are an insurance fraud investigation assistant for auto claims.

Your job is to help a human investigator review suspicious claims.
You do not make final fraud decisions.
You must only use the facts provided in the input.
Do not invent missing facts.
Do not assume fraud unless supported by evidence in the claim data.

Return ONLY valid JSON.
Do not add markdown.
Do not add explanations outside JSON.

Required JSON schema:
{{
  "summary": "string",
  "inconsistencies": ["string"],
  "risk_factors": ["string"],
  "evidence": ["string"],
  "recommended_review_priority": "low|medium|high",
  "investigator_note": "string"
}}

Field rules:
- summary:
  - max 70 words
  - concise, factual, neutral
- inconsistencies:
  - list contradictions between structured data, claimant narrative, and adjuster note
  - empty list if none found
- risk_factors:
  - list suspicious indicators, not conclusions
  - examples: "claim filed shortly after policy start", "repair estimate unusually high"
- evidence:
  - list only facts explicitly present in the input
- recommended_review_priority:
  - "high" if there is a strong inconsistency, multiple linked-entity signals, or several risk factors
  - "medium" if there are one or two moderate suspicious indicators without a major contradiction
  - "low" if the claim looks mostly consistent and only weak signals exist
- investigator_note:
  - max 90 words
  - explain why the case should or should not be prioritized for review
  - neutral and professional tone

Important constraints:
- Never say "fraud confirmed"
- Never mention facts not present in the input
- If the adjuster note explicitly says the damage does not match the claimant narrative, include that under inconsistencies
- If the claim was filed shortly after policy start, include that as a risk factor
- If the repair estimate is high, include that as a risk factor
- If linked claims counts are elevated, include that as a risk factor
- Base the final priority only on the provided data

Example 1:
Input:
{{
  "claim_id": "CLM-90001",
  "claim_type": "collision",
  "damage_area": "rear",
  "estimated_repair_cost": 5200,
  "incident_city": "Montreal",
  "days_since_policy_start": 420,
  "reporting_delay_days": 1,
  "prior_claims_12m": 0,
  "linked_claims_same_phone": 0,
  "linked_claims_same_repair_shop": 0,
  "claimant_narrative": "Another vehicle hit me from behind while I was stopped.",
  "adjuster_note": "Rear bumper damage observed. Damage appears consistent with claimant statement.",
  "rule_score": 1,
  "risk_level": "low",
  "rules_triggered": []
}}

Output:
{{
  "summary": "Rear-end collision claim reported one day after the incident. Adjuster observations are consistent with the claimant narrative, and no major suspicious indicators are present.",
  "inconsistencies": [],
  "risk_factors": [],
  "evidence": [
    "Claim reported one day after the incident",
    "Rear bumper damage observed",
    "Adjuster note says damage is consistent with claimant statement",
    "No linked entity signals are present"
  ],
  "recommended_review_priority": "low",
  "investigator_note": "The claim appears internally consistent based on the narrative, damage observations, and absence of notable linkage or history indicators. Review can be deprioritized unless additional external evidence emerges."
}}

Example 2:
Input:
{{
  "claim_id": "CLM-90002",
  "claim_type": "collision",
  "damage_area": "rear",
  "estimated_repair_cost": 5100,
  "incident_city": "Longueuil",
  "days_since_policy_start": 600,
  "reporting_delay_days": 4,
  "prior_claims_12m": 0,
  "linked_claims_same_phone": 0,
  "linked_claims_same_repair_shop": 0,
  "claimant_narrative": "Another car hit me from behind while I was waiting in traffic.",
  "adjuster_note": "Inspection found primary damage on the front-left side. Damage pattern does not match the claimant statement.",
  "rule_score": 7,
  "risk_level": "high",
  "rules_triggered": ["narrative inconsistency detected"]
}}

Output:
{{
  "summary": "Collision claim contains a major inconsistency between the reported rear impact and the front-left damage observed during inspection.",
  "inconsistencies": [
    "Claimant described a rear impact, but the adjuster observed primary front-left damage"
  ],
  "risk_factors": [
    "material inconsistency between narrative and observed damage"
  ],
  "evidence": [
    "Claimant narrative describes a rear-end impact",
    "Adjuster note states primary damage is on the front-left side",
    "Adjuster note says the damage does not match the claimant statement"
  ],
  "recommended_review_priority": "high",
  "investigator_note": "This claim should be prioritized because the core incident description conflicts with the observed damage pattern. The inconsistency is material and directly relevant to claim plausibility."
}}

Example 3:
Input:
{{
  "claim_id": "CLM-90003",
  "claim_type": "collision",
  "damage_area": "side",
  "estimated_repair_cost": 11800,
  "incident_city": "Laval",
  "days_since_policy_start": 6,
  "reporting_delay_days": 2,
  "prior_claims_12m": 3,
  "linked_claims_same_phone": 4,
  "linked_claims_same_repair_shop": 7,
  "claimant_narrative": "I lost control and hit a barrier on the side of the road.",
  "adjuster_note": "Limited visible damage. Estimate appears elevated given observed condition. Repeated entity pattern detected across recent claims.",
  "rule_score": 10,
  "risk_level": "high",
  "rules_triggered": [
    "claim filed shortly after policy start",
    "repair estimate above normal threshold",
    "multiple prior claims in the last 12 months",
    "same phone number linked to multiple claims",
    "repair shop linked to multiple claims"
  ]
}}

Output:
{{
  "summary": "This collision claim presents several elevated risk indicators, including filing shortly after policy start, a high repair estimate, prior claims history, and repeated linked entities.",
  "inconsistencies": [],
  "risk_factors": [
    "claim filed shortly after policy start",
    "repair estimate unusually high",
    "multiple prior claims in the last 12 months",
    "same phone number linked to multiple claims",
    "repair shop linked to multiple claims"
  ],
  "evidence": [
    "Days since policy start is 6",
    "Estimated repair cost is 11800",
    "Prior claims in last 12 months is 3",
    "Linked claims with same phone is 4",
    "Linked claims with same repair shop is 7",
    "Adjuster note says visible damage is limited relative to estimate"
  ],
  "recommended_review_priority": "high",
  "investigator_note": "The case should be reviewed as a priority because multiple independent risk indicators are present, including early policy timing, elevated repair cost, repeat linkage patterns, and prior claims history."
}}

Now analyze this claim and return ONLY valid JSON.

Input:
{json.dumps(claim_json, ensure_ascii=False, indent=2)}
"""


def build_repair_prompt(raw_output: str) -> str:
    return f"""
Convert the following text into valid JSON only.

Required schema:
{{
  "summary": "string",
  "inconsistencies": ["string"],
  "risk_factors": ["string"],
  "evidence": ["string"],
  "recommended_review_priority": "low|medium|high",
  "investigator_note": "string"
}}

Text:
{raw_output}
"""


def call_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9
            }
        },
        timeout=120
    )
    response.raise_for_status()
    data = response.json()
    return data["response"]


def extract_json_object(raw_text: str):
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    return None


def normalize_output(parsed: dict) -> dict:
    return {
        "summary": str(parsed.get("summary", "")).strip(),
        "inconsistencies": parsed.get("inconsistencies", []) if isinstance(parsed.get("inconsistencies", []), list) else [],
        "risk_factors": parsed.get("risk_factors", []) if isinstance(parsed.get("risk_factors", []), list) else [],
        "evidence": parsed.get("evidence", []) if isinstance(parsed.get("evidence", []), list) else [],
        "recommended_review_priority": parsed.get("recommended_review_priority", "medium")
        if parsed.get("recommended_review_priority", "medium") in {"low", "medium", "high"}
        else "medium",
        "investigator_note": str(parsed.get("investigator_note", "")).strip(),
    }


def fallback_output(raw_output: str) -> dict:
    return {
        "summary": raw_output[:500].strip(),
        "inconsistencies": [],
        "risk_factors": [],
        "evidence": [],
        "recommended_review_priority": "medium",
        "investigator_note": "Model output could not be parsed as structured JSON. Manual review recommended."
    }


def process_claim(claim: dict) -> dict:
    prompt = build_prompt(claim)
    raw_output = call_ollama(prompt)

    parsed = extract_json_object(raw_output)

    if parsed is None:
        repair_prompt = build_repair_prompt(raw_output)
        repaired_output = call_ollama(repair_prompt)
        parsed = extract_json_object(repaired_output)

    if parsed is None:
        normalized = fallback_output(raw_output)
    else:
        normalized = normalize_output(parsed)

    return {
        "claim": claim,
        "llm_output": normalized
    }


def process_claims() -> None:
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file '{INPUT_FILE}' not found. Run fraud_scoring_pipeline.py first."
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    results = []

    for line in tqdm(lines, desc="Enriching flagged claims"):
        claim = json.loads(line)
        enriched = process_claim(claim)
        results.append(enriched)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Saved enriched claims to {OUTPUT_FILE}")
    print(f"Processed {len(results)} claims using model: {MODEL}")


if __name__ == "__main__":
    process_claims()