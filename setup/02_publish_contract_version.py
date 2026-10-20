# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Publish a new version (simulates the data owner's change)
# MAGIC - **excel** (default): copies `demo/spec_versions/cargo_shipments.<version>.xlsx` over `specs/cargo_shipments.xlsx`
# MAGIC   — the owner edited the spreadsheet; Genie Code then regenerates the contract from it.
# MAGIC - **contract**: copies `demo/contract_versions/cargo_shipments.<version>.yaml` over `contracts/cargo_shipments.odcs.yaml`
# MAGIC   — skips the Excel step (fallback, or to show the pipeline skill's own breaking-change stop).

# COMMAND ----------

dbutils.widgets.dropdown("what", "excel", ["excel", "contract"], "Publish")
dbutils.widgets.dropdown("version", "v1.1.0", ["v1.0.0", "v1.1.0", "v2.0.0", "v1.2.0-mislabelled"], "Contract version")
VERSION = dbutils.widgets.get("version")

# COMMAND ----------

import os, shutil
from pathlib import Path
root = Path(os.getcwd()).parent
if dbutils.widgets.get("what") == "excel":
    src = root / "demo" / "spec_versions" / f"cargo_shipments.{VERSION}.xlsx"
    dst = root / "specs" / "cargo_shipments.xlsx"
else:
    src = root / "demo" / "contract_versions" / f"cargo_shipments.{VERSION}.yaml"
    dst = root / "contracts" / "cargo_shipments.odcs.yaml"
shutil.copyfile(src, dst)
print(f"published {src.name} -> {dst}")
