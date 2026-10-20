# Databricks notebook source
# MAGIC %md
# MAGIC # Regression tests for the skill's contract tools
# MAGIC Run after changing the skill or a contract version. Pure Python, any compute.

# COMMAND ----------

# MAGIC %pip install -q openpyxl pyyaml

# COMMAND ----------

import os, runpy, sys
for t in ("test_contract_tools.py", "test_excel_contract.py"):
    sys.argv = [t]
    runpy.run_path(os.path.join(os.getcwd(), t), run_name="__main__")
