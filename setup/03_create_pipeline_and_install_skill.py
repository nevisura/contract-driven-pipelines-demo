# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Create the pipeline and install the skill (by code)
# MAGIC Run after `00_setup_environment`. Safe to re-run: updates the pipeline and re-syncs the skill.
# MAGIC - Creates/updates the Lakeflow pipeline `cargo_shipments_contract_demo` (serverless, triggered, dev mode)
# MAGIC - Copies `skills/contract-driven-pipeline` into **your** `/Users/<you>/.assistant/skills/`
# MAGIC   (Genie Code loads that folder automatically — no settings needed). Each presenter runs this once.

# COMMAND ----------

# MAGIC %pip install -q --upgrade databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "tc_demo", "Catalog")
dbutils.widgets.text("pipeline_name", "cargo_shipments_contract_demo", "Pipeline name")
CATALOG = dbutils.widgets.get("catalog").strip()
NAME = dbutils.widgets.get("pipeline_name").strip()

import os, shutil
from pathlib import Path
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.pipelines import PipelineLibrary, PathPattern

w = WorkspaceClient()
ME = w.current_user.me().user_name
REPO = Path(os.getcwd()).parent                     # this notebook lives in <repo>/setup
ROOT = str(REPO / "pipelines" / "cargo_shipments")
LANDING = f"/Volumes/{CATALOG}/cargo_landing/raw/shipments"
assert (REPO / "contracts" / "cargo_shipments.odcs.yaml").exists(), f"repo not found at {REPO}"
print("repo:", REPO, "| user:", ME)

# COMMAND ----------

# 1) Pipeline — create, or update if one with this name exists
spec = dict(
    name=NAME,
    catalog=CATALOG,
    schema="cargo",
    serverless=True,
    continuous=False,
    development=True,
    root_path=ROOT,
    libraries=[PipelineLibrary(glob=PathPattern(include=f"{ROOT}/transformations/**"))],
    configuration={"cargo.landing_path": LANDING},
)
existing = [p for p in w.pipelines.list_pipelines(filter=f"name LIKE '{NAME}'") if p.name == NAME]
if existing:
    pid = existing[0].pipeline_id
    w.pipelines.update(pipeline_id=pid, **spec)
    print("updated pipeline", pid)
else:
    pid = w.pipelines.create(**spec).pipeline_id
    print("created pipeline", pid)
print(f"open it: {w.config.host}/pipelines/{pid}")

# COMMAND ----------

# 2) Skill — copy the repo's skill into your personal Genie Code skills folder
src = REPO / "skills" / "contract-driven-pipeline"
dst = Path(f"/Workspace/Users/{ME}/.assistant/skills/contract-driven-pipeline")
if dst.exists():
    shutil.rmtree(dst)                                 # replace stale copy (single source = the repo)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
print("skill installed ->", dst)
for f in sorted(dst.rglob("*")):
    if f.is_file():
        print("  ", f.relative_to(dst))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC 1. Open the pipeline link above → Genie Code pane → **new chat** → **Agent mode**.
# MAGIC 2. Type `@` and check `contract-driven-pipeline` is suggested (hard-refresh the tab if not).
# MAGIC 3. Prompt (path printed below):

# COMMAND ----------

print(f"@contract-driven-pipeline Build the pipeline for {REPO / 'contracts' / 'cargo_shipments.odcs.yaml'}")
