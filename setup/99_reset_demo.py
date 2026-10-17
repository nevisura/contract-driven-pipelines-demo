# Databricks notebook source
# MAGIC %md
# MAGIC # 99 · Reset the demo to the starting point
# MAGIC Removes landed files and generated code, restores contract v1.0.0.
# MAGIC Simplest alternative: keep a Git tag/branch `demo-start` and reset the Git folder to it.
# MAGIC
# MAGIC **Tables**: afterwards open the pipeline and run **Full refresh all** once batch 1 is landed again,
# MAGIC or delete and re-create the pipeline (deleting a UC pipeline drops its tables).

# COMMAND ----------

dbutils.widgets.text("catalog", "tc_demo", "Catalog")
dbutils.widgets.dropdown("confirm", "no", ["no", "yes"], "Really reset?")
CATALOG = dbutils.widgets.get("catalog")
assert dbutils.widgets.get("confirm") == "yes", "Set 'Really reset?' to yes"

# COMMAND ----------

import os, shutil
from pathlib import Path
root = Path(os.getcwd()).parent

landing = f"/Volumes/{CATALOG}/cargo_landing/raw/shipments"
dbutils.fs.rm(landing, recurse=True); dbutils.fs.mkdirs(landing)
print("cleared", landing)

shutil.copyfile(root / "demo/contract_versions/cargo_shipments.v1.0.0.yaml", root / "contracts/cargo_shipments.odcs.yaml")
print("contract restored to v1.0.0")

for p in [root / "contracts/_applied/cargo_shipments.odcs.yaml",
          root / "pipelines/cargo_shipments/transformations/cargo_shipments.py",
          root / "pipelines/cargo_shipments/governance/apply_uc_governance.sql"]:
    if p.exists():
        p.unlink(); print("removed", p)
