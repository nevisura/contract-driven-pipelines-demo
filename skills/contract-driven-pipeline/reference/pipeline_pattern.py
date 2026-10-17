# =============================================================================
# GENERATED FROM DATA CONTRACT — DO NOT EDIT BY HAND
# contract : flight_legs  (id 9b0e11d2-flight-legs)  version 1.0.0
# source   : reference/example_contract.yaml
# skill    : contract-driven-pipeline
# To change this pipeline, change the contract and ask Genie Code to apply it.
# =============================================================================
#
# REFERENCE PATTERN — copy the STRUCTURE, not the content.
# Every UPPER_CASE constant below is checked by `contract_tools.py check`:
#   CONTRACT_ID / CONTRACT_VERSION   literal values from the contract
#   TABLE_PROPERTIES                 contract.id, contract.name, contract.version
#   BRONZE_SCHEMA                    every contract property as STRING, contract order
#   BRONZE_EXPECTATIONS              exactly {"no_undeclared_fields": "_rescued_data IS NULL"}
#   SILVER_SCHEMA                    one column per line: name TYPE COMMENT '<contract description>',
#                                    contract order, then the three audit columns
#   ERROR_RULES / WARNING_RULES /    exactly the rules printed by `contract_tools.py expectations`,
#   CRITICAL_RULES                   predicates copied verbatim
# =============================================================================
from pyspark import pipelines as dp
from pyspark.sql import functions as F

CONTRACT_ID = "9b0e11d2-flight-legs"
CONTRACT_VERSION = "1.0.0"
LANDING_PATH = spark.conf.get("network.landing_path")  # never hard-code a path

TABLE_PROPERTIES = {
    "contract.id": CONTRACT_ID,
    "contract.name": "flight_legs",
    "contract.version": CONTRACT_VERSION,
}

BRONZE_SCHEMA = "flight_number STRING, departure_ts STRING, seats STRING"

BRONZE_EXPECTATIONS = {"no_undeclared_fields": "_rescued_data IS NULL"}

SILVER_SCHEMA = """
flight_number STRING COMMENT 'Carrier code + flight number.',
departure_ts TIMESTAMP COMMENT 'Scheduled departure (UTC).',
seats INT COMMENT 'Seats offered on the leg.',
_ingest_ts TIMESTAMP COMMENT 'Time the record was ingested by the pipeline.',
_source_file STRING COMMENT 'Landing file the record was read from.',
_contract_version STRING COMMENT 'Data contract version the record was validated against.'
"""

ERROR_RULES = {  # severity error -> dropped from silver, kept in quarantine
    "flight_number_not_null": "flight_number IS NOT NULL",
    "flight_number_format": "flight_number IS NULL OR flight_number RLIKE '^[A-Z0-9]{2}[0-9]{1,4}$'",
    "departure_ts_not_null": "departure_ts IS NOT NULL",
    "seats_range": "seats IS NULL OR (seats >= 0)",
}
WARNING_RULES = {  # severity warning -> kept, tracked in pipeline metrics
    "departure_after_2000": "coalesce((departure_ts >= TIMESTAMP'2000-01-01'), FALSE)",
}
CRITICAL_RULES = {}  # severity critical -> update fails (add @dp.expect_all_or_fail when non-empty)


def _typed(df):
    """Cast bronze strings to contract types with try_cast (bad values -> NULL -> rule violation)."""
    return df.select(
        F.col("flight_number"),                                       # STRING: no cast
        F.expr("try_cast(departure_ts AS TIMESTAMP)").alias("departure_ts"),
        F.expr("try_cast(seats AS INT)").alias("seats"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
        F.lit(CONTRACT_VERSION).alias("_contract_version"),
    )


@dp.table(
    name="bronze_flight_legs",
    comment="Raw flight legs as landed (all fields STRING). Contract flight_legs.",
    table_properties={**TABLE_PROPERTIES, "quality": "bronze"},
)
@dp.expect_all(BRONZE_EXPECTATIONS)
def bronze_flight_legs():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("rescuedDataColumn", "_rescued_data")   # undeclared fields stay visible here
        .schema(BRONZE_SCHEMA)
        .load(LANDING_PATH)
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )


@dp.table(
    name="silver_flight_legs",
    comment="Typed scheduled flight legs.",                    # = contract object description
    schema=SILVER_SCHEMA,
    table_properties={**TABLE_PROPERTIES, "quality": "silver"},
)
@dp.expect_all_or_drop(ERROR_RULES)
@dp.expect_all(WARNING_RULES)
def silver_flight_legs():
    return _typed(spark.readStream.table("bronze_flight_legs"))


@dp.table(
    name="silver_flight_legs_quarantine",
    comment="Rows rejected by error-severity contract rules, with the rules they failed.",
    table_properties={**TABLE_PROPERTIES, "quality": "quarantine"},
)
def silver_flight_legs_quarantine():
    failed = F.array_compact(F.array(*[
        F.when(~F.coalesce(F.expr(pred), F.lit(False)), F.lit(name))
        for name, pred in ERROR_RULES.items()
    ]))
    return (
        _typed(spark.readStream.table("bronze_flight_legs"))
        .withColumn("_failed_rules", failed)
        .where(F.size("_failed_rules") > 0)
    )
