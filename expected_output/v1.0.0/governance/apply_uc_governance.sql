-- Databricks notebook source
-- GENERATED FROM DATA CONTRACT cargo_shipments v1.0.0 by contract_tools.py — DO NOT EDIT BY HAND
-- Applies Unity Catalog tags derived from the contract. Run after the pipeline update
-- (tags cannot be set from inside pipeline code). Column comments come from the pipeline schema.

-- COMMAND ----------

-- table: silver_cargo_shipments
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments SET TAGS ('contract_id' = '4f1c2a7e-cargo-shipments', 'contract_version' = '1.0.0', 'domain' = 'cargo', 'data_product' = 'cargo-operations', 'quality' = 'silver', 'cargo' = 'true', 'awb' = 'true', 'operational' = 'true', 'classification' = 'confidential');

-- COMMAND ----------

-- columns
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN awb_number SET TAGS ('classification' = 'internal');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN status_code SET TAGS ('classification' = 'public');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN event_ts SET TAGS ('classification' = 'public');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN origin_airport SET TAGS ('classification' = 'public');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN destination_airport SET TAGS ('classification' = 'public');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN flight_number SET TAGS ('classification' = 'public');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN pieces SET TAGS ('classification' = 'public');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN weight_kg SET TAGS ('classification' = 'internal');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN commodity_description SET TAGS ('classification' = 'internal');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN shipper_name SET TAGS ('classification' = 'confidential', 'pii' = 'true');
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments ALTER COLUMN shipper_country SET TAGS ('classification' = 'internal');

-- COMMAND ----------

-- quarantine inherits the most sensitive classification
ALTER STREAMING TABLE tc_demo.cargo.silver_cargo_shipments_quarantine SET TAGS ('contract_id' = '4f1c2a7e-cargo-shipments', 'contract_version' = '1.0.0', 'quality' = 'quarantine', 'classification' = 'confidential');
