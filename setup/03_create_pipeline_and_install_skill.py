# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Install the skills (and, only as a fallback, create the pipeline)
# MAGIC Run after `00_setup_environment`, once per presenter. Safe to re-run.
# MAGIC 1. Copies `skills/excel-to-data-contract` and `skills/contract-driven-pipeline` into **your** `/Users/<you>/.assistant/skills/` —
# MAGIC    Genie Code loads that folder automatically. Re-run after any change to the skill, then start a new chat.
# MAGIC 2. *(Fallback only)* creates the pipeline definition the same way the agent does in Act 1 (`contract_tools deploy`).
# MAGIC    Normally you **skip** this cell — creating the pipeline is the agent's job on stage.

# COMMAND ----------

import os, shutil, sys, importlib
from pathlib import Path

REPO = Path(os.getcwd()).parent                     # this notebook lives in <repo>/setup
SKILL_SRC = REPO / "skills" / "contract-driven-pipeline"
SKILLS = ["excel-to-data-contract", "contract-driven-pipeline"]
assert (SKILL_SRC / "SKILL.md").exists(), f"repo not found at {REPO}"
ME = spark.sql("SELECT current_user()").first()[0]
print("repo:", REPO, "| user:", ME)

# COMMAND ----------

# 1) Install / re-sync both skills into your personal Genie Code skills folder
#    (installed side by side: the Excel skill reuses the pipeline skill's validator and diff)
for skill in SKILLS:
    dst = Path(f"/Workspace/Users/{ME}/.assistant/skills/{skill}")
    if dst.exists():
        shutil.rmtree(dst)                             # the repo is the single source of truth
    shutil.copytree(REPO / "skills" / skill, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print("skill installed ->", dst)
    for f in sorted(dst.rglob("*")):
        if f.is_file():
            print("    ", f.relative_to(dst))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage prompts
# MAGIC Open `pipelines/cargo_shipments/explorations/contract_checks` → Genie Code pane → **new chat** → **Agent mode** →
# MAGIC type `@` to confirm both skills are listed → paste the prompts printed below.

# COMMAND ----------

C, X, P = REPO / "contracts" / "cargo_shipments.odcs.yaml", REPO / "specs" / "cargo_shipments.xlsx", REPO / "pipelines" / "cargo_shipments"
print("ACT 0  :", f"@excel-to-data-contract Create the data contract {C} from the Excel {X}")
print("ACT 1  :", f"@contract-driven-pipeline Build and deploy the pipeline for {C} (pipeline root: {P})")
print("ACT 2/3a:", f"@excel-to-data-contract The Excel {X} changed. Regenerate the data contract {C}.")
print("ACT 2/3b:", f"@contract-driven-pipeline The data contract {C} changed. Update the pipeline.")

# COMMAND ----------

# 2) FALLBACK ONLY — create the pipeline definition without the agent (same code path the agent uses)
RUN_FALLBACK = False
if RUN_FALLBACK:
    sys.path.insert(0, str(SKILL_SRC / "scripts"))
    import contract_tools as ct; importlib.reload(ct)
    ct.main(["deploy", str(REPO / "contracts" / "cargo_shipments.odcs.yaml"), str(REPO / "pipelines" / "cargo_shipments")])
