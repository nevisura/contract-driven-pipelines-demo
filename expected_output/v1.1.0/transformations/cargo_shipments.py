# =============================================================================
# GENERATED FROM DATA CONTRACT — DO NOT EDIT BY HAND
# contract : cargo_shipments  (id 4f1c2a7e-cargo-shipments)  version 1.1.0
# source   : contracts/cargo_shipments.odcs.yaml
# skill    : contract-driven-pipeline
# To change this pipeline, change the contract and ask Genie Code to apply it.
# =============================================================================
from pyspark import pipelines as dp
from pyspark.sql import functions as F

CONTRACT_ID = "4f1c2a7e-cargo-shipments"
CONTRACT_VERSION = "1.1.0"
LANDING_PATH = spark.conf.get("cargo.landing_path")

TABLE_PROPERTIES = {
    "contract.id": CONTRACT_ID,
    "contract.name": "cargo_shipments",
    "contract.version": CONTRACT_VERSION,
}

# Bronze lands every contract field as STRING; anything else goes to _rescued_data.
BRONZE_SCHEMA = (
    "awb_number STRING, status_code STRING, event_ts STRING, origin_airport STRING, "
    "destination_airport STRING, flight_number STRING, pieces STRING, weight_kg STRING, "
    "commodity_description STRING, dg_class STRING, shipper_name STRING, shipper_country STRING"
)

BRONZE_EXPECTATIONS = {"no_undeclared_fields": "_rescued_data IS NULL"}

SILVER_SCHEMA = """
awb_number STRING COMMENT 'IATA air waybill number, 3-digit airline prefix + 8-digit serial (e.g. 020-12345675).',
status_code STRING COMMENT 'IATA Cargo-IMP status code (BKD, RCS, MAN, DEP, ARR, RCF, NFD, DLV).',
event_ts TIMESTAMP COMMENT 'UTC timestamp at which the status event occurred.',
origin_airport STRING COMMENT 'IATA code of the origin airport.',
destination_airport STRING COMMENT 'IATA code of the destination airport.',
flight_number STRING COMMENT 'Carrier code + flight number of the leg, when known (e.g. LH8400).',
pieces INT COMMENT 'Number of pieces in the shipment.',
weight_kg DECIMAL(10,2) COMMENT 'Gross weight in kilograms, as declared on the AWB.',
commodity_description STRING COMMENT 'Free-text description of the goods.',
dg_class STRING COMMENT 'IATA dangerous goods hazard class with optional division (e.g. 3, 2.1). Null for non-DG shipments.',
shipper_name STRING COMMENT 'Name of the shipping party. Confidential — mask for non-cargo consumers.',
shipper_country STRING COMMENT 'ISO 3166-1 alpha-2 country code of the shipper.',
_ingest_ts TIMESTAMP COMMENT 'Time the record was ingested by the pipeline.',
_source_file STRING COMMENT 'Landing file the record was read from.',
_contract_version STRING COMMENT 'Data contract version the record was validated against.'
"""

# Contract rules -> expectations (from: contract_tools.py expectations <contract>)
ERROR_RULES = {  # severity error -> row dropped from silver, kept in quarantine
    "awb_number_not_null": "awb_number IS NOT NULL",
    "awb_number_format": "awb_number IS NULL OR awb_number RLIKE '^[0-9]{3}-[0-9]{8}$'",
    "status_code_not_null": "status_code IS NOT NULL",
    "event_ts_not_null": "event_ts IS NOT NULL",
    "origin_airport_not_null": "origin_airport IS NOT NULL",
    "origin_airport_format": "origin_airport IS NULL OR origin_airport RLIKE '^[A-Z]{3}$'",
    "destination_airport_not_null": "destination_airport IS NOT NULL",
    "destination_airport_format": "destination_airport IS NULL OR destination_airport RLIKE '^[A-Z]{3}$'",
    "flight_number_format": "flight_number IS NULL OR flight_number RLIKE '^[A-Z0-9]{2}[0-9]{1,4}[A-Z]?$'",
    "pieces_not_null": "pieces IS NOT NULL",
    "pieces_range": "pieces IS NULL OR (pieces >= 1)",
    "weight_kg_not_null": "weight_kg IS NOT NULL",
    "weight_kg_range": "weight_kg IS NULL OR (weight_kg > 0)",
    "dg_class_format": "dg_class IS NULL OR dg_class RLIKE '^[1-9]([.][1-6])?$'",
    "shipper_country_format": "shipper_country IS NULL OR shipper_country RLIKE '^[A-Z]{2}$'",
    "valid_status_code": "coalesce((status_code IN ('BKD','RCS','MAN','DEP','ARR','RCF','NFD','DLV')), FALSE)",
    "awb_check_digit": "coalesce((try_cast(substr(awb_number, 5, 7) AS BIGINT) % 7 = try_cast(substr(awb_number, 12, 1) AS INT)), FALSE)",
    "origin_differs_from_destination": "coalesce((origin_airport <> destination_airport), FALSE)",
}
WARNING_RULES = {  # severity warning -> row kept, violation tracked in pipeline metrics
    "event_not_in_future": "coalesce((event_ts <= current_timestamp() + INTERVAL 1 HOUR), FALSE)",
}
CRITICAL_RULES = {}  # severity critical -> update fails


def _typed(df):
    """Cast bronze strings to contract types. try_cast: bad values become NULL and fail a rule."""
    return df.select(
        F.col("awb_number"),
        F.col("status_code"),
        F.expr("try_cast(event_ts AS TIMESTAMP)").alias("event_ts"),
        F.col("origin_airport"),
        F.col("destination_airport"),
        F.col("flight_number"),
        F.expr("try_cast(pieces AS INT)").alias("pieces"),
        F.expr("try_cast(weight_kg AS DECIMAL(10,2))").alias("weight_kg"),
        F.col("commodity_description"),
        F.col("dg_class"),
        F.col("shipper_name"),
        F.col("shipper_country"),
        F.col("_ingest_ts"),
        F.col("_source_file"),
        F.lit(CONTRACT_VERSION).alias("_contract_version"),
    )


@dp.table(
    name="bronze_cargo_shipments",
    comment="Raw AWB status events as landed (all fields STRING). Contract cargo_shipments.",
    table_properties={**TABLE_PROPERTIES, "quality": "bronze"},
)
@dp.expect_all(BRONZE_EXPECTATIONS)
def bronze_cargo_shipments():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("rescuedDataColumn", "_rescued_data")
        .schema(BRONZE_SCHEMA)
        .load(LANDING_PATH)
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )


@dp.table(
    name="silver_cargo_shipments",
    comment="Typed, validated AWB status events.",
    schema=SILVER_SCHEMA,
    table_properties={**TABLE_PROPERTIES, "quality": "silver"},
)
@dp.expect_all_or_drop(ERROR_RULES)
@dp.expect_all(WARNING_RULES)
def silver_cargo_shipments():
    return _typed(spark.readStream.table("bronze_cargo_shipments"))


@dp.table(
    name="silver_cargo_shipments_quarantine",
    comment="Rows rejected by error-severity contract rules, with the rules they failed.",
    table_properties={**TABLE_PROPERTIES, "quality": "quarantine"},
)
def silver_cargo_shipments_quarantine():
    failed = F.array_compact(F.array(*[
        F.when(~F.coalesce(F.expr(pred), F.lit(False)), F.lit(name))
        for name, pred in ERROR_RULES.items()
    ]))
    return (
        _typed(spark.readStream.table("bronze_cargo_shipments"))
        .withColumn("_failed_rules", failed)
        .where(F.size("_failed_rules") > 0)
    )
