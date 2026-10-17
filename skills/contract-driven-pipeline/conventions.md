# Team conventions for contract-driven pipelines

These are the rules a senior engineer would otherwise enforce in review.
`scripts/contract_tools.py check` verifies every rule marked ✔.

## Layering and naming
- ✔ One Lakeflow declarative pipeline file per contract: `transformations/<contract name>.py`.
- ✔ Three streaming tables per contract schema object `<entity>`:
  - `bronze_<entity>` — raw, every contract field as `STRING`, plus `_rescued_data`, `_ingest_ts`, `_source_file`.
  - `silver_<entity>` — the contract's `physicalName`; typed, validated, documented.
  - `silver_<entity>_quarantine` — rows rejected by error-severity rules, with `_failed_rules` (array of rule names).
- Gold / aggregates are **not** generated from a source contract; they belong to the consumer's contract.
- Catalog and schema come from the pipeline settings (contract `servers` entry), never from code.

## Code
- ✔ `from pyspark import pipelines as dp` (not `import dlt`).
- ✔ No hard-coded storage paths (`/Volumes/`, `abfss://`, `dbfs:/`, `s3://`). Read the landing path with `spark.conf.get("<sourcePathConf>")`.
- ✔ Dataset functions only return DataFrames: no `collect()`, `count()`, `toPandas()`, `saveAsTable()`, `start()`, no `spark.sql("ALTER ...")`.
- Keep the constant block (`CONTRACT_ID`, `CONTRACT_VERSION`, `TABLE_PROPERTIES`, `BRONZE_SCHEMA`, `BRONZE_EXPECTATIONS`, `SILVER_SCHEMA`, `ERROR_RULES`, `WARNING_RULES`, `CRITICAL_RULES`) at the top, in this order — reviewers read the contract mapping there.
- Column order everywhere = contract order. Audit columns last.

## Ingestion (bronze)
- ✔ Auto Loader with an explicit all-STRING schema, `cloudFiles.schemaEvolutionMode = rescue` and `rescuedDataColumn = _rescued_data`. Fields the contract doesn't declare end up in `_rescued_data` — visible, never silently dropped, never silently promoted to columns.
- ✔ `@dp.expect_all(BRONZE_EXPECTATIONS)` with exactly `{"no_undeclared_fields": "_rescued_data IS NULL"}` (warning only: tells us the producer has drifted from the contract).

## Typing and validation (silver)
- ✔ Cast with `try_cast(...)` only. Under ANSI mode a plain `CAST` on a bad value fails the whole update; with `try_cast` it becomes `NULL` and a contract rule rejects the row.
- ✔ Explicit `schema=SILVER_SCHEMA` with `COMMENT` = contract description for every column.
- ✔ Expectations come only from `contract_tools.py expectations`:
  | Contract severity | Decorator | Effect |
  |---|---|---|
  | `error` (default for `required`, `pattern`, `minimum`/`maximum`) | `@dp.expect_all_or_drop(ERROR_RULES)` | dropped from silver, kept in quarantine |
  | `warning` | `@dp.expect_all(WARNING_RULES)` | kept, counted in pipeline metrics |
  | `critical` | `@dp.expect_all_or_fail(CRITICAL_RULES)` | update stops |
- ✔ Quarantine evaluates the same `ERROR_RULES` with `coalesce(pred, FALSE)` so NULL counts as a failure.

## Metadata and governance
- ✔ `table_properties` on every table: `contract.id`, `contract.name`, `contract.version`, `quality` (`bronze` / `silver` / `quarantine`).
- ✔ Audit column `_contract_version` on every silver row.
- ✔ Unity Catalog tags (table: contract id/version, domain, data product, highest classification; column: classification + contract tags such as `pii`) are applied by the generated `governance/apply_uc_governance.sql` notebook after the pipeline update. Tags cannot be set from inside pipeline code.
- Column masks / row filters for `confidential` and `restricted` columns are owned by the platform team; flag such columns in the summary, don't invent masking functions.

## Change management
- Contract diff decides: `METADATA` and `ADDITIVE` changes are applied as minimal edits; `BREAKING` changes and semver violations are **never** applied without explicit human sign-off.
- Generated code is reviewed like hand-written code: through a Git diff, by an engineer, before it runs in a shared environment.
