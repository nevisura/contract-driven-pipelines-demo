# Databricks notebook source
# MAGIC %md
# MAGIC # Regression tests for the skill's contract tools
# MAGIC Run after changing the skill or a contract version. Pure Python, any compute.

# COMMAND ----------

import os, runpy, sys
sys.argv = ["test_contract_tools.py"]
runpy.run_path(os.path.join(os.getcwd(), "test_contract_tools.py"), run_name="__main__")
