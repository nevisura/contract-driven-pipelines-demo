# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Publish a contract version (simulates the producer's merged contract PR)
# MAGIC Copies `demo/contract_versions/cargo_shipments.<version>.yaml` over the active contract
# MAGIC `contracts/cargo_shipments.odcs.yaml`. On stage you can instead paste the file content and show the Git diff.

# COMMAND ----------

dbutils.widgets.dropdown("version", "v1.1.0", ["v1.0.0", "v1.1.0", "v2.0.0", "v1.2.0-mislabelled"], "Contract version")
VERSION = dbutils.widgets.get("version")

# COMMAND ----------

import os, shutil
from pathlib import Path
root = Path(os.getcwd()).parent
src = root / "demo" / "contract_versions" / f"cargo_shipments.{VERSION}.yaml"
dst = root / "contracts" / "cargo_shipments.odcs.yaml"
shutil.copyfile(src, dst)
print(f"published {src.name} -> {dst}")
