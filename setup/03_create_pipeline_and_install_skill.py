# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Install the skill (and, only as a fallback, create the pipeline)
# MAGIC Run after `00_setup_environment`, once per presenter. Safe to re-run.
# MAGIC 1. Copies `skills/contract-driven-pipeline` into **your** `/Users/<you>/.assistant/skills/` —
# MAGIC    Genie Code loads that folder automatically. Re-run after any change to the skill, then start a new chat.
# MAGIC 2. *(Fallback only)* creates the pipeline definition the same way the agent does in Act 1 (`contract_tools deploy`).
# MAGIC    Normally you **skip** this cell — creating the pipeline is the agent's job on stage.

# COMMAND ----------

import os, shutil, sys, importlib
from pathlib import Path

REPO = Path(os.getcwd()).parent                     # this notebook lives in <repo>/setup
SKILL_SRC = REPO / "skills" / "contract-driven-pipeline"
assert (SKILL_SRC / "SKILL.md").exists(), f"repo not found at {REPO}"
ME = spark.sql("SELECT current_user()").first()[0]
print("repo:", REPO, "| user:", ME)

# COMMAND ----------

# 1) Install / re-sync the skill into your personal Genie Code skills folder
dst = Path(f"/Workspace/Users/{ME}/.assistant/skills/contract-driven-pipeline")
if dst.exists():
    shutil.rmtree(dst)                                 # the repo is the single source of truth
shutil.copytree(SKILL_SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
print("skill installed ->", dst)
for f in sorted(dst.rglob("*")):
    if f.is_file():
        print("  ", f.relative_to(dst))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Act 1 prompt
# MAGIC Open `pipelines/cargo_shipments/explorations/contract_checks` → Genie Code pane → **new chat** → **Agent mode** →
# MAGIC type `@` to confirm `contract-driven-pipeline` is listed → paste the prompt printed below.

# COMMAND ----------

print(f"@contract-driven-pipeline Build and deploy the pipeline for {REPO / 'contracts' / 'cargo_shipments.odcs.yaml'} "
      f"(pipeline root: {REPO / 'pipelines' / 'cargo_shipments'})")

# COMMAND ----------

# 2) FALLBACK ONLY — create the pipeline definition without the agent (same code path the agent uses)
RUN_FALLBACK = False
if RUN_FALLBACK:
    sys.path.insert(0, str(SKILL_SRC / "scripts"))
    import contract_tools as ct; importlib.reload(ct)
    ct.main(["deploy", str(REPO / "contracts" / "cargo_shipments.odcs.yaml"), str(REPO / "pipelines" / "cargo_shipments")])
