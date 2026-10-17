# Databricks notebook source
# MAGIC %md
# MAGIC # Verify demo state (dry run / before recording)
# MAGIC Pick the stage you just finished; the cell asserts the numbers the audience will see.
# MAGIC Counts are deterministic (seeded generator in `setup/demo_data.py`).

# COMMAND ----------

dbutils.widgets.text("catalog", "tc_demo", "Catalog")
dbutils.widgets.dropdown("stage", "act1_v1_batch1",
                         ["act1_v1_batch1", "act2_v1_batch1+2", "act2_v1.1_full_refresh"], "Stage")
C, STAGE = dbutils.widgets.get("catalog"), dbutils.widgets.get("stage")

# COMMAND ----------

def n(sql):
    return spark.sql(sql).first()[0]

t = f"{C}.cargo"
got = {
    "bronze": n(f"SELECT count(*) FROM {t}.bronze_cargo_shipments"),
    "silver": n(f"SELECT count(*) FROM {t}.silver_cargo_shipments"),
    "quarantine": n(f"SELECT count(*) FROM {t}.silver_cargo_shipments_quarantine"),
    "rescued": n(f"SELECT count(*) FROM {t}.bronze_cargo_shipments WHERE _rescued_data IS NOT NULL"),
    "versions": sorted(r[0] for r in spark.sql(f"SELECT DISTINCT _contract_version FROM {t}.silver_cargo_shipments").collect()),
}
expected = {
    "act1_v1_batch1":         {"bronze": 476, "silver": 452, "quarantine": 24, "versions": ["1.0.0"]},
    "act2_v1_batch1+2":       {"bronze": 667, "silver": 619, "quarantine": 48, "versions": ["1.0.0"]},
    "act2_v1.1_full_refresh": {"bronze": 667, "silver": 617, "quarantine": 50, "versions": ["1.1.0"]},
}[STAGE]
print("got:", got)
for k, v in expected.items():
    assert got[k] == v, f"{k}: expected {v}, got {got[k]}"
if STAGE == "act2_v1_batch1+2":
    assert got["rescued"] > 0, "batch 2 should show undeclared fields in _rescued_data"
if STAGE == "act2_v1.1_full_refresh":
    assert got["rescued"] == 0
    assert n(f"SELECT count(dg_class) FROM {t}.silver_cargo_shipments") == 39
    assert n(f"SELECT count(*) FROM {t}.silver_cargo_shipments_quarantine WHERE array_contains(_failed_rules, 'dg_class_format')") == 2
print(f"✅ {STAGE}: demo state as expected")
