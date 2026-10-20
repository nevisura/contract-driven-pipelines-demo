# Databricks notebook source
# MAGIC %md
# MAGIC # 99 · Reset the demo to the starting point
# MAGIC Removes landed files and generated code, restores contract v1.0.0.
# MAGIC Simplest alternative: keep a Git tag/branch `demo-start` and reset the Git folder to it.
# MAGIC
# MAGIC Also deletes the pipeline `cargo_shipments_pipeline` (and with it its tables) — the agent re-creates it in Act 1.

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

# COMMAND ----------

from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
for p in w.pipelines.list_pipelines(filter="name LIKE 'cargo_shipments_pipeline'"):
    if p.name == "cargo_shipments_pipeline":
        w.pipelines.delete(pipeline_id=p.pipeline_id)
        print("deleted pipeline", p.pipeline_id, "(its tables are dropped with it)")
