import csv
import random
from datetime import datetime, timedelta
from collections import defaultdict

random.seed(42)

CITIES = ["Montreal", "Laval", "Longueuil", "Quebec City", "Gatineau", "Sherbrooke"]
CLAIM_TYPES = ["collision", "theft", "vandalism"]
DAMAGE_AREAS = ["front", "rear", "left side", "right side"]
REPAIR_SHOPS = [f"SHOP-{i:03d}" for i in range(1, 31)]

NORMAL_NARRATIVES = [
    "I was stopped at a light and another vehicle hit me from behind.",
    "A car changed lanes and struck the side of my vehicle.",
    "I hit a guardrail after losing control on a snowy road.",
    "My parked car was damaged while I was inside a store.",
]

NORMAL_ADJUSTER_NOTES = [
    "Damage appears consistent with claimant statement. Estimate is within expected range.",
    "Observed damage aligns with reported incident details.",
    "Claim details and visible damage are coherent.",
]

SUSPICIOUS_NOTES = [
    "Visible damage appears limited relative to the repair estimate.",
    "Damage pattern appears inconsistent with claimant statement.",
    "Claim shares characteristics with previously flagged files.",
    "Reported sequence of events lacks detail and supporting evidence.",
]

FIRST_NAMES = ["Alex", "Sam", "Chris", "Taylor", "Jordan", "Pat", "Jamie", "Morgan"]
LAST_NAMES = ["Tremblay", "Gagnon", "Roy", "Cote", "Bouchard", "Morin", "Lavoie", "Fortin"]
VEHICLES = [
    ("Toyota", "Corolla"),
    ("Honda", "Civic"),
    ("Ford", "Escape"),
    ("Nissan", "Altima"),
    ("Hyundai", "Elantra"),
    ("Mazda", "CX-5"),
    ("Chevrolet", "Malibu"),
]

TODAY = datetime(2026, 3, 23)

def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def fmt_date(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")

def gen_phone() -> str:
    area = random.choice(["438", "514", "450"])
    return f"{area}-555-{random.randint(1000, 9999)}"

def gen_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def make_claimant_narrative(claim_type: str, damage_area: str, city: str) -> str:
    if claim_type == "collision":
        templates = [
            f"I was driving in {city} when another vehicle hit the {damage_area} of my car.",
            f"I lost control briefly and damaged the {damage_area} of my vehicle in {city}.",
            f"Another driver struck my vehicle on the {damage_area} while I was driving in {city}.",
        ]
    elif claim_type == "theft":
        templates = [
            f"My car was stolen in {city} and later found with damage.",
            f"I discovered my vehicle missing in {city} and reported it immediately.",
        ]
    else:
        templates = [
            f"My parked car was vandalized in {city} and the {damage_area} was damaged.",
            f"I found damage on the {damage_area} of my vehicle while parked in {city}.",
        ]
    return random.choice(templates)

def make_adjuster_note(normal: bool = True) -> str:
    return random.choice(NORMAL_ADJUSTER_NOTES if normal else SUSPICIOUS_NOTES)

def repair_cost_base(claim_type: str, damage_area: str) -> int:
    if claim_type == "theft":
        return random.randint(5000, 12000)
    if damage_area in ["front", "rear"]:
        return random.randint(1800, 4500)
    return random.randint(1500, 4000)

def generate_base_record(claim_id_num: int):
    claim_id = f"CLM-{claim_id_num:05d}"
    policy_id = f"POL-{random.randint(1000, 9999)}"
    claimant_id = f"CUST-{random.randint(1000, 9999)}"
    repair_shop_id = random.choice(REPAIR_SHOPS)

    policy_start = random_date(datetime(2024, 1, 1), datetime(2025, 12, 31))
    incident_date = random_date(policy_start + timedelta(days=30), TODAY - timedelta(days=1))
    report_delay = random.randint(0, 5)
    claim_report_date = incident_date + timedelta(days=report_delay)

    claim_type = random.choice(CLAIM_TYPES)
    damage_area = random.choice(DAMAGE_AREAS)
    estimated_repair_cost = repair_cost_base(claim_type, damage_area)
    incident_city = random.choice(CITIES)

    return {
        "claim_id": claim_id,
        "policy_id": policy_id,
        "claimant_id": claimant_id,
        "repair_shop_id": repair_shop_id,
        "policy_start_date": fmt_date(policy_start),
        "incident_date": fmt_date(incident_date),
        "claim_report_date": fmt_date(claim_report_date),
        "claim_type": claim_type,
        "damage_area": damage_area,
        "estimated_repair_cost": estimated_repair_cost,
        "incident_city": incident_city,
        "prior_claims_12m": random.randint(0, 1),
        "linked_claims_same_phone": 0,
        "linked_claims_same_repair_shop": 0,
        "claimant_narrative": make_claimant_narrative(claim_type, damage_area, incident_city),
        "adjuster_note": make_adjuster_note(normal=True),
        "fraud_pattern_type": "normal",
        "is_suspicious": 0,
        # helper fields not exported unless wanted
        "_claimant_phone": gen_phone(),
        "_claimant_name": gen_name(),
    }

def apply_early_policy(record):
    policy_start = datetime.strptime(record["policy_start_date"], "%Y-%m-%d")
    incident_date = policy_start + timedelta(days=random.randint(2, 10))
    report_date = incident_date + timedelta(days=random.randint(1, 5))

    record["incident_date"] = fmt_date(incident_date)
    record["claim_report_date"] = fmt_date(report_date)
    record["estimated_repair_cost"] = random.randint(7000, 12000)
    record["adjuster_note"] = random.choice([
        "Claim filed shortly after policy inception. Damage appears less severe than estimated cost suggests.",
        "Limited visible damage. Estimate appears elevated given observed condition.",
    ])
    record["fraud_pattern_type"] = "early_policy"
    record["is_suspicious"] = 1

def apply_inflated_repair(record):
    record["estimated_repair_cost"] = random.randint(8000, 15000)
    record["adjuster_note"] = random.choice([
        "Repair estimate is significantly above expected range for the reported damage.",
        "Observed damage appears moderate, but submitted estimate is unusually high.",
    ])
    record["fraud_pattern_type"] = "inflated_repair"
    record["is_suspicious"] = 1

def apply_repeated_entity(record, hot_phone, hot_shop):
    record["_claimant_phone"] = hot_phone
    record["repair_shop_id"] = hot_shop
    record["prior_claims_12m"] = random.randint(2, 4)
    record["linked_claims_same_phone"] = random.randint(2, 6)
    record["linked_claims_same_repair_shop"] = random.randint(4, 10)
    record["adjuster_note"] = random.choice([
        "Claim linked to multiple prior files sharing the same contact number and repair shop.",
        "Repeated entity pattern detected across recent claims.",
    ])
    record["fraud_pattern_type"] = "repeated_entity"
    record["is_suspicious"] = 1

def apply_narrative_inconsistency(record):
    original_damage = record["damage_area"]
    inconsistent_damage = random.choice([d for d in DAMAGE_AREAS if d != original_damage])

    record["claimant_narrative"] = f"Another vehicle struck me on the {original_damage} in {record['incident_city']}."
    record["adjuster_note"] = (
        f"Inspection found primary damage on the {inconsistent_damage}. "
        f"Damage pattern does not match the claimant statement."
    )
    record["fraud_pattern_type"] = "narrative_inconsistency"
    record["is_suspicious"] = 1

def apply_mixed(record, hot_phone, hot_shop):
    apply_early_policy(record)
    record["_claimant_phone"] = hot_phone
    record["repair_shop_id"] = hot_shop
    record["prior_claims_12m"] = random.randint(2, 5)
    record["linked_claims_same_phone"] = random.randint(3, 7)
    record["linked_claims_same_repair_shop"] = random.randint(5, 12)
    record["estimated_repair_cost"] = random.randint(9000, 16000)
    original_damage = record["damage_area"]
    inconsistent_damage = random.choice([d for d in DAMAGE_AREAS if d != original_damage])
    record["claimant_narrative"] = f"I was hit on the {original_damage} while driving in {record['incident_city']}."
    record["adjuster_note"] = (
        f"Claim reported shortly after policy start. Estimate is unusually high. "
        f"Observed damage on the {inconsistent_damage}, inconsistent with claimant statement. "
        f"Repair shop is linked to several flagged claims."
    )
    record["fraud_pattern_type"] = "mixed"
    record["is_suspicious"] = 1

def generate_dataset(
    total_claims=1000,
    output_file="synthetic_auto_claims.csv",
    ratios=None
):
    """
    ratios: dict with keys
    normal, early_policy, inflated_repair, repeated_entity,
    narrative_inconsistency, mixed
    """
    if ratios is None:
        ratios = {
            "normal": 0.60,
            "early_policy": 0.15,
            "inflated_repair": 0.10,
            "repeated_entity": 0.08,
            "narrative_inconsistency": 0.05,
            "mixed": 0.02,
        }

    counts = {k: int(total_claims * v) for k, v in ratios.items()}
    assigned = sum(counts.values())
    counts["normal"] += total_claims - assigned  # adjust rounding

    records = []
    claim_id_num = 1

    hot_phones = [gen_phone() for _ in range(5)]
    hot_shops = random.sample(REPAIR_SHOPS, 3)

    for _ in range(counts["normal"]):
        records.append(generate_base_record(claim_id_num))
        claim_id_num += 1

    for _ in range(counts["early_policy"]):
        r = generate_base_record(claim_id_num)
        apply_early_policy(r)
        records.append(r)
        claim_id_num += 1

    for _ in range(counts["inflated_repair"]):
        r = generate_base_record(claim_id_num)
        apply_inflated_repair(r)
        records.append(r)
        claim_id_num += 1

    for _ in range(counts["repeated_entity"]):
        r = generate_base_record(claim_id_num)
        apply_repeated_entity(r, random.choice(hot_phones), random.choice(hot_shops))
        records.append(r)
        claim_id_num += 1

    for _ in range(counts["narrative_inconsistency"]):
        r = generate_base_record(claim_id_num)
        apply_narrative_inconsistency(r)
        records.append(r)
        claim_id_num += 1

    for _ in range(counts["mixed"]):
        r = generate_base_record(claim_id_num)
        apply_mixed(r, random.choice(hot_phones), random.choice(hot_shops))
        records.append(r)
        claim_id_num += 1

    random.shuffle(records)

    # recompute actual linked counts based on generated hot entities for better consistency
    phone_count = defaultdict(int)
    shop_count = defaultdict(int)
    for r in records:
        phone_count[r["_claimant_phone"]] += 1
        shop_count[r["repair_shop_id"]] += 1

    for r in records:
        r["linked_claims_same_phone"] = max(0, phone_count[r["_claimant_phone"]] - 1)
        r["linked_claims_same_repair_shop"] = max(0, shop_count[r["repair_shop_id"]] - 1)

        # keep normal records less suspicious-looking
        if r["fraud_pattern_type"] == "normal":
            r["linked_claims_same_phone"] = min(r["linked_claims_same_phone"], 1)
            r["linked_claims_same_repair_shop"] = min(r["linked_claims_same_repair_shop"], 2)

    fieldnames = [
        "claim_id",
        "policy_id",
        "claimant_id",
        "repair_shop_id",
        "policy_start_date",
        "incident_date",
        "claim_report_date",
        "claim_type",
        "damage_area",
        "estimated_repair_cost",
        "incident_city",
        "prior_claims_12m",
        "linked_claims_same_phone",
        "linked_claims_same_repair_shop",
        "claimant_narrative",
        "adjuster_note",
        "fraud_pattern_type",
        "is_suspicious",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r[k] for k in fieldnames})

    print(f"Generated {len(records)} claims into {output_file}")

if __name__ == "__main__":
    generate_dataset(total_claims=1000, output_file="synthetic_auto_claims.csv")