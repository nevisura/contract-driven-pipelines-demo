# Databricks notebook source
# MAGIC %md
# MAGIC # Contract checks & demo queries
# MAGIC Genie Code runs the skill's tools here; the presenter uses the queries below to show results.
# MAGIC Every cell is safe to run by hand if the agent is slow on stage.

# COMMAND ----------

dbutils.widgets.text("catalog", "tc_demo", "Catalog")
CATALOG = dbutils.widgets.get("catalog")

import os, sys, importlib
from pathlib import Path
ROOT = Path(os.getcwd()).parents[2]          # <repo>/pipelines/cargo_shipments/explorations -> <repo>
SKILL_DIR = ROOT / "skills" / "contract-driven-pipeline"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import contract_tools as ct; importlib.reload(ct)

CONTRACT = str(ROOT / "contracts" / "cargo_shipments.odcs.yaml")
SNAPSHOT = str(ROOT / "contracts" / "_applied" / "cargo_shipments.odcs.yaml")
PIPELINE = str(ROOT / "pipelines" / "cargo_shipments" / "transformations" / "cargo_shipments.py")
GOVERNANCE = str(ROOT / "pipelines" / "cargo_shipments" / "governance" / "apply_uc_governance.sql")
PIPELINE_ROOT = str(ROOT / "pipelines" / "cargo_shipments")

# COMMAND ----------

ct.main(["validate", CONTRACT])

# COMMAND ----------

ct.main(["expectations", CONTRACT])

# COMMAND ----------

# UPDATE mode only (needs the applied snapshot)
ct.main(["diff", SNAPSHOT, CONTRACT])

# COMMAND ----------

ct.main(["check", CONTRACT, PIPELINE, "--governance", GOVERNANCE])

# COMMAND ----------

# Create the pipeline definition from the contract (dev mode; never starts a run). Add "--dry-run" to preview.
ct.main(["deploy", CONTRACT, PIPELINE_ROOT])

# COMMAND ----------

# MAGIC %md ## Show the results

# COMMAND ----------

# Why rows were rejected
display(spark.sql(f"""
  SELECT rule, count(*) AS rows
  FROM {CATALOG}.cargo.silver_cargo_shipments_quarantine LATERAL VIEW explode(_failed_rules) t AS rule
  GROUP BY rule ORDER BY rows DESC"""))

# COMMAND ----------

# Producer drift: fields the contract doesn't declare (batch 2 before contract v1.1.0)
display(spark.sql(f"""
  SELECT _rescued_data, count(*) AS rows
  FROM {CATALOG}.cargo.bronze_cargo_shipments
  WHERE _rescued_data IS NOT NULL GROUP BY _rescued_data ORDER BY rows DESC LIMIT 10"""))

# COMMAND ----------

# Which contract version validated the data
display(spark.sql(f"""
  SELECT _contract_version, count(*) AS rows, count(dg_class) AS rows_with_dg_class
  FROM {CATALOG}.cargo.silver_cargo_shipments GROUP BY _contract_version"""))

# COMMAND ----------

# Governance: table properties + UC tags derived from the contract
display(spark.sql(f"SHOW TBLPROPERTIES {CATALOG}.cargo.silver_cargo_shipments").where("key LIKE 'contract.%' OR key = 'quality'"))
display(spark.sql(f"""
  SELECT column_name, tag_name, tag_value FROM {CATALOG}.information_schema.column_tags
  WHERE schema_name = 'cargo' AND table_name = 'silver_cargo_shipments' ORDER BY column_name, tag_name"""))
display(spark.sql(f"""
  SELECT tag_name, tag_value FROM {CATALOG}.information_schema.table_tags
  WHERE schema_name = 'cargo' AND table_name = 'silver_cargo_shipments' ORDER BY tag_name"""))

# COMMAND ----------

# Apply governance from here if the .sql file doesn't open as a runnable notebook/editor tab
stmts = [s.strip() for s in "\n".join(l for l in Path(GOVERNANCE).read_text().splitlines()
                                      if not l.strip().startswith("--")).split(";") if s.strip()]
for s in stmts:
    spark.sql(s)
print(f"applied {len(stmts)} governance statements")
