"""
Deterministic, fictional AWB status events for the demo.

batch 1 — producer still on contract v1.0.0, ~6% bad rows (each bad row breaks one known rule)
batch 2 — producer has started sending `dg_class` (not yet in the contract!)
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

AIRPORTS = ["FRA", "MUC", "TIA", "JFK", "ORD", "PVG", "NRT", "DXB", "GRU", "JNB", "BOM", "SIN", "LAX", "MEX", "CAI"]
STATUS_FLOW = ["BKD", "RCS", "MAN", "DEP", "ARR", "RCF", "NFD", "DLV"]
PREFIXES = ["020", "020", "020", "724", "157"]  # mostly 020; all fictional usage
SHIPPERS = [  # invented company names
    ("Nordlicht Instruments GmbH", "DE"), ("Adriatik Textile Sh.p.k.", "AL"), ("Lakeview Pharma Inc.", "US"),
    ("Sakura Precision KK", "JP"), ("Rio Verde Flowers Ltda", "BR"), ("Harbor Lane Electronics", "SG"),
    ("Danube Auto Parts AG", "AT"), ("Cedar Point Medical", "US"), ("Monsoon Spices Pvt Ltd", "IN"),
    ("Atlas Machinery SA", "MA"),
]
COMMODITIES = ["machine parts", "garments", "pharmaceuticals", "electronics", "fresh flowers", "auto parts",
               "medical devices", "spices", "documents", "lithium batteries", "perfume", "paint"]
DG_FOR = {"lithium batteries": "9", "perfume": "3", "paint": "3", "pharmaceuticals": "6.1"}


def _awb(rng: random.Random) -> str:
    serial7 = rng.randint(1_000_000, 9_999_999)
    return f"{rng.choice(PREFIXES)}-{serial7}{serial7 % 7}"


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _events(rng: random.Random, n_awbs: int, start: datetime, with_dg: bool) -> list[dict]:
    rows = []
    for _ in range(n_awbs):
        awb = _awb(rng)
        o, d = rng.sample(AIRPORTS, 2)
        pieces = rng.randint(1, 40)
        weight = round(pieces * rng.uniform(2.5, 60.0), 2)
        shipper, country = rng.choice(SHIPPERS)
        commodity = rng.choice(COMMODITIES)
        flight = f"LH{rng.randint(8000, 8999)}"
        ts = start + timedelta(minutes=rng.randint(0, 60 * 24))
        for status in STATUS_FLOW[: rng.randint(2, len(STATUS_FLOW))]:
            ts += timedelta(minutes=rng.randint(20, 300))
            row = {
                "awb_number": awb, "status_code": status, "event_ts": _iso(ts),
                "origin_airport": o, "destination_airport": d,
                "flight_number": flight if status in ("MAN", "DEP", "ARR", "RCF") else None,
                "pieces": pieces, "weight_kg": weight, "commodity_description": commodity,
                "shipper_name": shipper, "shipper_country": country,
            }
            if with_dg:
                row["dg_class"] = DG_FOR.get(commodity)
            rows.append(row)
    return rows


# Each corruption breaks exactly one contract rule, so the quarantine tells a clear story.
CORRUPTIONS = [
    ("awb_number_not_null", lambda r: r.update(awb_number=None)),
    ("awb_number_format", lambda r: r.update(awb_number=r["awb_number"].replace("-", ""))),
    ("awb_check_digit", lambda r: r.update(awb_number=r["awb_number"][:-1] + str((int(r["awb_number"][-1]) + 1) % 7))),
    ("valid_status_code", lambda r: r.update(status_code="XXX")),
    ("origin_airport_format", lambda r: r.update(origin_airport="Fra")),
    ("origin_differs_from_destination", lambda r: r.update(destination_airport=r["origin_airport"])),
    ("pieces_range", lambda r: r.update(pieces=0)),
    ("weight_kg_range", lambda r: r.update(weight_kg=-12.5)),
    ("weight_kg_not_null", lambda r: r.update(weight_kg="n/a")),          # try_cast -> NULL
    ("event_ts_not_null", lambda r: r.update(event_ts="yesterday")),      # try_cast -> NULL
    ("shipper_country_format", lambda r: r.update(shipper_country="Germany")),
    ("flight_number_format", lambda r: r.update(flight_number="LH-8400")),
]


def batch(n: int, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    rng = random.Random(20261022 + n)
    if n == 1:
        rows = _events(rng, 90, now - timedelta(days=4), with_dg=False)
    elif n == 2:
        rows = _events(rng, 40, now - timedelta(days=3), with_dg=True)
    else:
        raise ValueError("batch must be 1 or 2")
    # keep every awb_check_digit corruption on a valid-format AWB whose last digit actually changes
    targets = rng.sample(range(len(rows)), k=len(CORRUPTIONS) * 2)
    for i, idx in enumerate(targets):
        _, fn = CORRUPTIONS[i % len(CORRUPTIONS)]
        fn(rows[idx])
    # two events in the future -> warning only (kept in silver)
    for idx in rng.sample([i for i in range(len(rows)) if i not in targets], 2):
        rows[idx]["event_ts"] = _iso(now + timedelta(days=2))
    if n == 2:
        # two invalid DG classes for the v1.1.0 rule
        dg_rows = [i for i, r in enumerate(rows) if r.get("dg_class") and i not in targets]
        for idx in dg_rows[:2]:
            rows[idx]["dg_class"] = "3.9"
    return rows


def to_jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"


if __name__ == "__main__":
    import sys
    from pathlib import Path
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "landing")
    out.mkdir(parents=True, exist_ok=True)
    for b in (1, 2):
        rows = batch(b)
        (out / f"batch_{b:03d}.json").write_text(to_jsonl(rows), encoding="utf-8")
        print(f"batch {b}: {len(rows)} rows -> {out / f'batch_{b:03d}.json'}")
