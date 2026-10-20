# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Set up the demo environment
# MAGIC Creates the landing volume and the target schema, and points the contracts at your catalog.
# MAGIC Run once, the day before. Serverless or any UC-enabled compute (DBR 15.4+).

# COMMAND ----------

# MAGIC %pip install -q openpyxl pyyaml

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
    new = re.sub(r"/Volumes/[^/]+/cargo_landing/", f"/Volumes/{CATALOG}/cargo_landing/", new)
    if new != txt:
        Path(f).write_text(new)
        print("catalog updated in", f)
print(f"{len(files)} contract files point at catalog '{CATALOG}'")

# Same for the Excel specs (the Excel is the source the contracts are generated from)
import sys
sys.path.insert(0, str(REPO_ROOT / "skills" / "excel-to-data-contract" / "scripts"))
import excel_contract as xc
specs = [*glob.glob(str(REPO_ROOT / "specs" / "*.xlsx")), *glob.glob(str(REPO_ROOT / "demo" / "spec_versions" / "*.xlsx"))]
for f in specs:
    xc.set_field(f, "catalog", CATALOG)
    xc.set_field(f, "source_path", LANDING)
print(f"{len(specs)} Excel specs point at catalog '{CATALOG}'")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC Run `03_create_pipeline_and_install_skill` once per presenter — it installs the Genie Code skill.
# MAGIC **The pipeline itself is created by the agent** in Act 1 (skill step `deploy`).
# MAGIC Commit the contract files if the catalog changed.

# COMMAND ----------

print("landing path (in the contracts):", LANDING)
print("pipeline target:", CATALOG, "/ cargo — created by the agent from the contract")
