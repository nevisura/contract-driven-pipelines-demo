# Excel → ODCS v3 mapping (team profile)

One workbook = one contract = one dataset. Sheet and header names are case-insensitive.

## Sheet `Contract` (column A = field, column B = value)

| Field | Contract | Notes |
|---|---|---|
| `name` * | `name`, `schema[0].name`, `physicalName: silver_<name>` | snake_case |
| `version` | `version` | blank → proposed from the change (patch / minor / major) |
| `id` | `id` | blank → kept from the previous contract, else derived (copy it back into the Excel) |
| `status` | `status` | default `active` |
| `domain` * · `data_product` · `tenant` | `domain` · `dataProduct` · `tenant` | |
| `purpose` * · `usage` · `limitations` | `description.purpose / usage / limitations` | |
| `dataset_business_name` · `dataset_description` * · `dataset_granularity` · `dataset_tags` | `schema[0].businessName / description / dataGranularityDescription / tags` | description = table comment |
| `server` · `environment` · `catalog` * · `schema` * | `servers[0]` (type `databricks`) | where the pipeline publishes |
| `source_format` · `source_path_conf` * · `source_path` * | `customProperties` `sourceFormat / sourcePathConf / sourcePath` | where the pipeline reads |
| `latency_value` · `latency_unit` · `latency_column` | `slaProperties` latency (`element: <name>.<column>`) | |
| `retention_value` · `retention_unit` | `slaProperties` retention | |

\* required

## Sheet `Columns` (one row per column, in output order)

| Header | Contract property | Accepted values |
|---|---|---|
| `name` * | `name` | snake_case, unique |
| `business_name` | `businessName` | |
| `logical_type` * | `logicalType` | string, integer, number, boolean, date, timestamp |
| `physical_type` | `physicalType` | STRING, INT, BIGINT, SMALLINT, BOOLEAN, DATE, TIMESTAMP, DOUBLE, DECIMAL(p,s); blank → default for the logical type |
| `required` * | `required` | yes/no (also y, x, true, 1 / n, false, 0, blank) |
| `primary_key_position` | `primaryKey: true`, `primaryKeyPosition` | 1..n without gaps; key columns must be required |
| `classification` * | `classification` | public, internal, confidential, restricted (blank → internal + warning) |
| `tags` | `tags` | comma-separated, lowercase_with_underscores (e.g. `pii`) |
| `description` * | `description` | becomes the column comment |
| `pattern` | `logicalTypeOptions.pattern` | regex; prefer `[0-9]`, `[.]` over backslashes |
| `minimum` · `exclusive_minimum` · `maximum` · `exclusive_maximum` | `logicalTypeOptions.*` | numbers |
| `example` | `examples` | comma-separated |

## Sheet `Quality` (business rules beyond the column checks)

| Header | Contract | Notes |
|---|---|---|
| `name` * | `quality[].name` | snake_case, unique, not clashing with derived names (`<col>_not_null`, `<col>_format`, `<col>_range`) |
| `description` | `description` | |
| `dimension` | `dimension` | accuracy, conformity, consistency, completeness, timeliness, uniqueness |
| `severity` | `severity` | error (default) → quarantine · warning → tracked · critical → update stops |
| `sql_predicate` * | `type: custom`, `engine: sql-predicate`, `implementation` | SQL boolean, TRUE = valid; `try_cast` only |

## Sheets `Team` and `Roles`
`Team`: `username`, `role` → `team[]`. `Roles`: `role`, `access` (read / write) → `roles[]`.

## Common fixes for the owner
| Message | Fix in Excel |
|---|---|
| `column 'AWB Number' must be snake_case` | rename to `awb_number` (consumers see this name) |
| `required must be yes/no` | use the dropdown |
| `primary key column 'x' must be required` | set `required` = yes |
| `use try_cast, not CAST` | rewrite the predicate with `try_cast(...)` |
| `semver violation` | clear the `version` cell (the tool proposes it) or raise it to the required bump |
| `BREAKING change — not written` | keep the old column during a deprecation period, or get owner sign-off |
