# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Land a batch of AWB status events (simulates the producer)
# MAGIC - **batch 1** — producer on contract v1.0.0 (≈5% bad rows, each breaking one known rule)
# MAGIC - **batch 2** — producer has started sending `dg_class`, which the contract doesn't have yet

# COMMAND ----------

dbutils.widgets.text("catalog", "tc_demo", "Catalog")
dbutils.widgets.dropdown("batch", "1", ["1", "2"], "Batch")
CATALOG, BATCH = dbutils.widgets.get("catalog"), int(dbutils.widgets.get("batch"))

# COMMAND ----------

import os, sys, importlib
sys.path.insert(0, os.getcwd())
import demo_data; importlib.reload(demo_data)

rows = demo_data.batch(BATCH)
path = f"/Volumes/{CATALOG}/cargo_landing/raw/shipments/batch_{BATCH:03d}.json"
with open(path, "w", encoding="utf-8") as fh:
    fh.write(demo_data.to_jsonl(rows))
print(f"landed {len(rows)} events -> {path}")

# COMMAND ----------

display(spark.read.json(path).limit(10))
