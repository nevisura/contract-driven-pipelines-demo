# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Set up the demo environment
# MAGIC Creates the landing volume and the target schema, and points the contracts at your catalog.
# MAGIC Run once, the day before. Serverless or any UC-enabled compute (DBR 15.4+).

# COMMAND ----------

dbutils.widgets.text("catalog", "tc_demo", "Catalog (must exist or you need CREATE CATALOG)")
dbutils.widgets.dropdown("create_catalog", "no", ["no", "yes"], "Create catalog if missing")
CATALOG = dbutils.widgets.get("catalog").strip()

# COMMAND ----------

import os, re, glob
from pathlib import Path

REPO_ROOT = Path(os.getcwd()).parent          # notebook runs from <repo>/setup
assert (REPO_ROOT / "contracts").exists(), f"Run this notebook from the repo's setup/ folder (cwd={os.getcwd()})"

if dbutils.widgets.get("create_catalog") == "yes":
    spark.sql(f"CREATE CATALOG IF NOT EXISTS `{CATALOG}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.cargo_landing COMMENT 'Landing zone for the TECH Connect demo'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.cargo_landing.raw")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.cargo COMMENT 'Contract-driven pipeline target (TECH Connect demo)'")
LANDING = f"/Volumes/{CATALOG}/cargo_landing/raw/shipments"
dbutils.fs.mkdirs(LANDING)
print("landing path:", LANDING)

# COMMAND ----------

# The contract's `servers` entry is the source of truth for where the pipeline publishes.
# If you use a catalog other than tc_demo, rewrite it in every contract file (active + demo versions).
files = [*glob.glob(str(REPO_ROOT / "contracts" / "*.yaml")), *glob.glob(str(REPO_ROOT / "demo" / "contract_versions" / "*.yaml"))]
for f in files:
    txt = Path(f).read_text()
    new = re.sub(r"(\n    catalog: ).*", rf"\g<1>{CATALOG}", txt, count=1)
    if new != txt:
        Path(f).write_text(new)
        print("catalog updated in", f)
print(f"{len(files)} contract files point at catalog '{CATALOG}'")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create the pipeline (UI, 2 minutes)
# MAGIC 1. **Jobs & Pipelines → Create → ETL pipeline**, name `cargo_shipments_contract_demo`.
# MAGIC 2. *Root folder*: `<this repo>/pipelines/cargo_shipments` (choose **existing folder**, keep the empty `transformations/`).
# MAGIC 3. *Default catalog / schema*: the catalog above / `cargo`. *Compute*: serverless. *Mode*: triggered.
# MAGIC 4. *Settings → Configuration*: add `cargo.landing_path` = the landing path printed above.
# MAGIC 5. Don't run it yet — the transformations folder is empty until Genie Code builds it.
# MAGIC
# MAGIC ## Register the skill (Genie Code pane → Settings)
# MAGIC **Add folder** → `<this repo>/skills` (the *parent* folder, not the skill folder). Toggle `contract-driven-pipeline` on.
# MAGIC Start a new chat afterwards — skills load at chat start.

# COMMAND ----------

print("pipeline configuration:\n  cargo.landing_path =", LANDING)
print("default catalog / schema:", CATALOG, "/ cargo")
print("skills folder to register:", REPO_ROOT / "skills")
