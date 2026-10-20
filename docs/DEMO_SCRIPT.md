# Demo script — "Write the Contract, Let the Agent Build the Pipeline"

Slot: 15–20 min · live demo ≈ 11 min · recorded fallback for every act.
Two skills, one chain: **Excel spec → data contract → pipeline**.
All prompts below are printed with your exact paths by `setup/03_create_pipeline_and_install_skill`.

## Before you go on stage (T-30 min)

- [ ] `setup/99_reset_demo` run with **start_from = excel** (no contract, no pipeline, Excel spec v1.0.0); batch 1 landed (`setup/01_land_batch`, batch=1).
- [ ] Jobs & Pipelines shows **no** `cargo_shipments_pipeline`. Serverless warmed (run any notebook cell once).
- [ ] Both skills installed via `setup/03` (re-run after any skill change); Genie Code **new chat open**, Agent mode on; `@` lists `excel-to-data-contract` and `contract-driven-pipeline`.
- [ ] Tabs, left to right:
  1. `specs/cargo_shipments.xlsx` (download/open in Excel, or show the sheets in the file preview)
  2. `skills/` folder — both `SKILL.md` files
  3. `pipelines/cargo_shipments/explorations/contract_checks` with the Genie Code pane open (all acts are prompted here)
  4. Jobs & Pipelines list (the new pipeline appears here)
  5. `setup/01_land_batch` (batch 2 preselected) and `setup/02_publish_contract_version` (Publish = excel)
  6. Catalog Explorer on `<catalog>.cargo`
  7. Fallback recordings, paused at 0:00
- [ ] Browser zoom 125–150 %, notifications off, Genie Code pane widened.

## 0:00 – 2:30 · Concept (slides)

- Pipelines are still handcrafted; standards live in wikis and heads; agreements are implicit.
- Unstructured AI makes this *faster but not better*.
- The chain: **spec (Excel) → contract = what → skill = how → agent does the work → engineer reviews**.

## 2:30 – 4:00 · Act 0 — the data owner's Excel becomes the contract

**Show (30 s)** tab 1: the workbook a data owner can fill without YAML — `Contract` sheet (name, domain, catalog, purpose),
`Columns` (one row per column: type, required, classification, pattern), `Quality` (business rules in plain SQL).

**Prompt (tab 3):**
```
@excel-to-data-contract Create the data contract <repo>/contracts/cargo_shipments.odcs.yaml from the Excel <repo>/specs/cargo_shipments.xlsx
```
Expected: dry run → no issues → **create v1.0.0** → validate PASS → summary with the next prompt.
Open the generated `contracts/cargo_shipments.odcs.yaml`: `version: 1.0.0`, the AWB `pattern`, `shipper_name` = confidential + `pii`, the `quality:` block.
> "The owner never touched YAML. And the contract is versioned and validated before anyone writes a line of pipeline code."

*(Optional, 20 s: show a pre-broken copy of the Excel — the tool points at `Columns!row 2: 'AWB Number' must be snake_case`.)*

## 4:00 – 8:00 · Act 1 — contract → running pipeline

**Show (20 s)** tab 2: `contract-driven-pipeline/SKILL.md` workflow — *"our senior engineer's review checklist, written once, versioned in Git."*

**Prompt (tab 3):**
```
@contract-driven-pipeline Build and deploy the pipeline for <repo>/contracts/cargo_shipments.odcs.yaml (pipeline root: <repo>/pipelines/cargo_shipments)
```
Narrate (≈ 2–4 min): validate PASS → CREATE → `expectations` (17 error rules, 1 warning) → writes `transformations/cargo_shipments.py`
→ governance notebook → **check** PASS (a self-correction is a feature — say so) → **deploy** creates `cargo_shipments_pipeline`
(catalog/schema and landing path from the contract, dev mode, *not started*) → snapshot → summary with the link.
> "Even the pipeline definition comes from the contract. What the agent does *not* do is press Run — that's me, after review."

**Review (30 s)** generated file: header with contract version, `ERROR_RULES`, `try_cast`, quarantine table.

**Run** — open the link (tab 4) → **Run pipeline**. Graph: **bronze 476 → silver 452, quarantine 24**. Silver → *Data quality* tab.
Tab 3: cells "Why rows were rejected" and "Which contract version" → then the **last cell (apply governance)** → "Governance" cell.
Tab 6: `shipper_name` tags `classification=confidential`, `pii=true`; table tag `contract_version=1.0.0`.

## 8:00 – 11:30 · Act 2 — the producer changes things (additive)

**Drift (60 s).** Tab 5: `01_land_batch` batch=2 → pipeline **Run** (incremental). Bronze shows **`no_undeclared_fields`**;
tab 3 "Producer drift" cell: rows carry `{"dg_class": "9"}`.
> "The producer started sending dangerous-goods classes. We saw it the same day — and nothing silently became a column."

**The owner updates the Excel (30 s).** `02_publish_contract_version` (Publish = excel, v1.1.0) — show the new `dg_class` row
in `Columns`, and that the **version cell is empty**.

**Prompt 1 — Excel → contract:**
```
@excel-to-data-contract The Excel <repo>/specs/cargo_shipments.xlsx changed. Regenerate the data contract <repo>/contracts/cargo_shipments.odcs.yaml.
```
Expected: **ADDITIVE** (new optional column + metadata) → **proposed 1.1.0** (minor bump, chosen by the tool) → written.

**Prompt 2 — contract → pipeline:**
```
@contract-driven-pipeline The data contract <repo>/contracts/cargo_shipments.odcs.yaml changed. Update the pipeline.
```
Expected: diff ADDITIVE → **minimal edit (~7 lines)** → check PASS → "full refresh needed". Show the Git diff; compare with `expected_output/v1.1.0`.

**Run** — **Full refresh all** → **silver 617, quarantine 50**; 39 rows with `dg_class`, 2 invalid `3.9` quarantined (`dg_class_format`).
Bronze warning gone. Apply governance again → `dangerous_goods` tag, `contract_version=1.1.0`.

## 11:30 – 13:00 · Act 3 — breaking change: two layers say no

`02_publish_contract_version` (Publish = excel, **v2.0.0**): `weight_kg` renamed, `commodity_description` deleted,
`shipper_country` now required — version cell empty.

```
@excel-to-data-contract The Excel <repo>/specs/cargo_shipments.xlsx changed. Regenerate the data contract <repo>/contracts/cargo_shipments.odcs.yaml.
```
Expected: **BREAKING — not written**: four changes (incl. "possible rename"), proposed 2.0.0, asks for the data owner's sign-off.
Contract and pipeline untouched.
> "The first gate is at the spec. Nobody's pipeline breaks because somebody edited a spreadsheet."

**Second layer (optional, 45 s):** `02_publish_contract_version` (Publish = **contract**, v2.0.0) — someone bypasses the Excel.
```
@contract-driven-pipeline The data contract <repo>/contracts/cargo_shipments.odcs.yaml changed. Update the pipeline.
```
Expected: **⛔ BREAKING CONTRACT CHANGE — not applied**, three options; Git shows **no files changed**.

**Bonus:** Publish = excel, `v1.2.0-mislabelled` (breaking change typed in as 1.2.0) → *semver violation: needs major*.

## 13:00 – 16:00 · Guardrails, limits, role (slides)

- Guardrails: validated spec → versioned contract → contract-derived expectations, UC comments/tags/properties → deterministic tools + self-check → breaking-change stops (twice) → human review via Git, human presses Run.
- **Genie ZeroOps** (private preview) as the operational counterpart: diagnoses failed runs, proposes fixes for approval. Talking point only.
- Limits seen in practice: non-deterministic form, context and token limits, review effort shifts to the engineer.
  (Background: we used Genie Code skills in a production platform migration on Databricks.)
- Role shift: from writing transformation code → owning specifications, encoding standards, reviewing agent output.

## 16:00 – 20:00 · Q&A

- *"Why Excel?"* — It's where data owners already describe datasets. The skill makes it a validated, versioned input; YAML stays the machine contract.
- *"Why not generate the code with a script entirely?"* — Contracts vary; the agent handles the variance, the tools pin down what must not vary.
- *"What if the agent ignores the skill?"* — `check` fails; the skill forbids handing over failing code; the reviewer sees FAIL.
- *"Where do consumers' contracts fit?"* — Gold tables get their own contracts; same pattern, different reference.

## If something goes wrong

| Symptom | Do this |
|---|---|
| A skill isn't picked up | It's `@`-mentioned; new chat; hard-refresh the tab; re-run `setup/03`. |
| Agent can't run notebook cells | Run the matching cell in `contract_checks` yourself (Excel convert, validate, check, deploy) — "the same tools the agent uses". |
| `openpyxl` missing | Run the `%pip install -q openpyxl pyyaml` cell at the top of `contract_checks`. |
| Excel step fails live | `setup/99_reset_demo` with start_from = contract was the plan B — or `02_publish_contract_version` with Publish = contract, and continue at Act 1 / prompt 2. |
| Agent is slow (> 3 min) | Talk through the SKILL.md; then switch to the recording for that act. |
| Generated pipeline fails `check` repeatedly | Copy `expected_output/<version>/…` into `transformations/` / `governance/`. |
| `deploy` fails | `RUN_FALLBACK = True` in `setup/03` and run that cell. |
| `ALTER STREAMING TABLE … SET TAGS` refused | Missing `APPLY TAG` / governed-tag policy — show the generated SQL and table properties instead. |
| Numbers differ from the script | `tests/verify_demo_state` for the stage; batch landed twice → reset. |

## Recording checklist (fallback)

Record each act separately (≤ 3 min each), 1080p, cursor highlight on, no audio — you narrate live.
Include: the Excel, each prompt being typed, the agent's tool calls and summary, the diffs, the pipeline graph with counts, the tags.
