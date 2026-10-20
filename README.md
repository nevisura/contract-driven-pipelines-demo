# Write the Contract, Let the Agent Build the Pipeline

Demo repository for the TECH Connect Day spotlight session (Tirana, 22 Oct 2026):
**contract-driven pipeline delivery with Databricks Genie Code skills.**

| Responsibility | Lives in | Says |
|---|---|---|
| **Data contract** (ODCS v3 YAML) | `contracts/cargo_shipments.odcs.yaml` | *what* the pipeline must deliver |
| **Genie Code skill** | `skills/contract-driven-pipeline/` | *how* our team builds pipelines |
| **Genie Code, Agent mode** | Lakeflow Pipelines Editor | generates and maintains the pipeline |

All data is fictional (invented shippers, randomised AWBs).

## Repository layout

```
contracts/
  cargo_shipments.odcs.yaml          active contract (what the producer has published)
  _applied/                          snapshot of the contract the current code was built from (agent writes it)
demo/contract_versions/              v1.0.0 · v1.1.0 (additive) · v2.0.0 (breaking) · v1.2.0-mislabelled (bonus)
skills/contract-driven-pipeline/
  SKILL.md                           workflow + guardrails the agent follows
  conventions.md                     team standards (layering, naming, try_cast, tags…)
  reference/                         worked example contract + the exact code pattern expected
  scripts/contract_tools.py          validate · expectations · diff · governance · check
pipelines/cargo_shipments/           pipeline root folder
  transformations/                   (empty) — Genie Code writes cargo_shipments.py here
  governance/                        (empty) — generated UC tag notebook
  explorations/contract_checks       runs the tools + the queries shown on stage
setup/                               00 environment · 01 land batch · 02 publish contract · 99 reset
tests/                               contract tool tests · verify_demo_state (asserts on-stage numbers)
expected_output/                     what the agent should produce for v1.0.0 and v1.1.0 (fallback + review aid)
docs/DEMO_SCRIPT.md                  run-of-show, exact prompts, talking points, fallbacks
```

## Setup (≈ 20 min, do it the day before)

**Prerequisites:** Unity Catalog workspace with serverless, Genie Code with Agent mode enabled,
privileges to create a schema + volume in a catalog, and `APPLY TAG` on the target schema.

1. **Push this repo** to your Git provider (Azure DevOps / GitHub) and **clone it into a Databricks Git folder**
   (*Workspace → Create → Git folder*).
2. Open `setup/00_setup_environment`, set the catalog (default `tc_demo`), *Run all*.
   It creates `<catalog>.cargo_landing.raw` (volume) and `<catalog>.cargo`, and points every contract at your catalog.
   Commit the contract change if the catalog isn't `tc_demo`.
3. **Create the pipeline and install the skill**: run `setup/03_create_pipeline_and_install_skill` (does both by code). Or by hand (*Jobs & Pipelines → Create → ETL pipeline*):
   name `cargo_shipments_contract_demo`, root folder `pipelines/cargo_shipments` (existing folder),
   default catalog `<catalog>` / schema `cargo`, serverless, triggered,
   configuration `cargo.landing_path = /Volumes/<catalog>/cargo_landing/raw/shipments`.
4. **Register the skill**: Genie Code pane → *Settings* → *Add folder* → `<repo>/skills`
   (the parent folder). Make sure `contract-driven-pipeline` is toggled on. Start a new chat.
5. Run `tests/run_contract_tests` → `all contract_tools tests passed`.
6. **Dry run the whole demo once** (docs/DEMO_SCRIPT.md), using `tests/verify_demo_state` after each act.
   Record it — that recording is your on-stage fallback.
7. Reset with `setup/99_reset_demo`, land batch 1 (`setup/01_land_batch`, batch = 1),
   then commit and create a branch `demo-start` so a reset is one Git operation.

## How the guardrails work

- **Deterministic where it matters.** Rule predicates, governance SQL and the contract diff come from
  `contract_tools.py`, not from the model. The agent assembles code; it doesn't invent rules.
- **Self-check.** `contract_tools.py check` parses the generated file (AST) and compares schema, comments,
  every expectation, table properties and conventions against the contract. The agent must reach PASS.
- **Breaking changes stop the agent.** `diff` classifies every change as METADATA / ADDITIVE / BREAKING and
  checks the semver bump. Breaking or mislabelled → no files touched, report for a human decision.
- **Producer drift is visible.** Bronze lands only declared fields; anything else goes to `_rescued_data`
  and trips the `no_undeclared_fields` expectation.
- **Quality from the contract.** `error` rules drop rows into a quarantine table with `_failed_rules`;
  `warning` rules are tracked; `critical` rules stop the update.
- **Governance from the contract.** Column comments from descriptions; UC tags (classification, `pii`,
  contract id/version) from the generated governance notebook; `contract.*` table properties on every table.
- **Human review.** Every change is a Git diff an engineer reviews before it runs.

## Known limits (say them on stage)

- Agent output is non-deterministic in form; `check` makes it deterministic in substance.
- Large contracts / many skills cost context and tokens; keep skills focused.
- Review effort moves to the engineer — it doesn't disappear.
- Unity Catalog tags can't be set from pipeline code, hence the separate governance step.
