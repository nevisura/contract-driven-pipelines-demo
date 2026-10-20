# Demo script — "Write the Contract, Let the Agent Build the Pipeline"

Slot: 15–20 min · live demo ≈ 9 min · recorded fallback for every act.

## Before you go on stage (T-30 min)

- [ ] Git folder on branch `demo-start`; `setup/99_reset_demo` run; batch 1 landed (`setup/01_land_batch`, batch=1).
- [ ] **No pipeline exists yet** (the agent creates it); delete `cargo_shipments_pipeline` if a rehearsal left one. Serverless warmed (run any notebook cell once).
- [ ] Genie Code: skill installed via `setup/03_create_pipeline_and_install_skill`, **new chat open**, Agent mode on.
- [ ] Tabs, left to right:
  1. `contracts/cargo_shipments.odcs.yaml`
  2. `skills/contract-driven-pipeline/SKILL.md`
  3. `pipelines/cargo_shipments/explorations/contract_checks` with the Genie Code pane open (Act 1 starts here)
  4. Jobs & Pipelines list (the new pipeline appears here)
  5. `setup/01_land_batch` (batch=2 preselected) and `setup/02_publish_contract_version`
  6. Catalog Explorer on `<catalog>.cargo`
  7. Fallback recording, paused at 0:00
- [ ] Browser zoom 125–150 %, notifications off, Genie Code pane widened.

## 0:00 – 3:00 · Concept (slides)

- Pipelines are still handcrafted: requirements → code, conventions re-implemented every project.
- Unstructured AI coding makes this *faster but not better*: plausible code, inconsistent with team standards, quality depends on the prompt.
- The question isn't *can an agent write a pipeline* but *how do we make agent output predictable, governed, maintainable*.
- Three responsibilities: **contract = what**, **skill = how**, **agent = does the work**, **engineer = reviews**.

## 3:00 – 7:30 · Act 1 — contract v1.0.0 → running pipeline

**Show (45 s)** tab 1, the contract. Point at: `version: 1.0.0`, `awb_number` with `pattern` and `primaryKey`,
`shipper_name` with `classification: confidential` + `pii`, the `quality:` block (`awb_check_digit`, `event_not_in_future` = warning).
> "This is the only thing the producer and I agree on. No ticket, no email."

**Show (30 s)** tab 2, the skill. Scroll SKILL.md workflow; flash `conventions.md` and `scripts/contract_tools.py`.
> "This is our senior engineer's review checklist — written once, versioned in Git, loaded by the agent."

**Prompt (tab 3, Genie Code, Agent mode)** — exact text is printed by `setup/03_…`:

```
@contract-driven-pipeline Build and deploy the pipeline for /Workspace/Users/nevis.ura@lhind.dlh.de/contract-driven-pipeline-demo/contracts/cargo_shipments.odcs.yaml (pipeline root: /Workspace/Users/nevis.ura@lhind.dlh.de/contract-driven-pipeline-demo/pipelines/cargo_shipments)
```

While it works (≈ 2–4 min), narrate what you see:
validate PASS → no snapshot → CREATE → `expectations` (17 error rules, 1 warning) → writes `transformations/cargo_shipments.py`
→ generates governance notebook → **check** (if it fails once and fixes itself, *great* — say so: "that's the guardrail working")
→ **deploy**: creates `cargo_shipments_pipeline` from the contract (catalog/schema from `servers`, landing path from `customProperties`, dev mode, *not started*)
→ writes the snapshot → summary table with the pipeline link.
> "Even the pipeline definition comes from the contract. What the agent does *not* do is press Run — that's my job, after review."

Open the link (tab 4) — the pipeline opens in the Lakeflow Pipelines Editor.

**Review (30 s)** — open the generated file: header with contract version, `ERROR_RULES` block, `try_cast`, quarantine table.
> "I review this like a colleague's PR. It's the same shape every time because the skill says so."

**Run** — *Run pipeline*. While it runs (≈ 1 min), explain the severity mapping (error → quarantine, warning → tracked, critical → stop).
Show the graph: **bronze 476 → silver 452, quarantine 24**. Click silver → *Data quality* tab: per-rule failures.

**Governance** — run `governance/apply_uc_governance.sql` (or the last cell of `contract_checks`).
Tab 6: `silver_cargo_shipments` → column `shipper_name` tags `classification=confidential`, `pii=true`; table tags `contract_version=1.0.0`.

*(Optional: `contract_checks` cell "Why rows were rejected".)*

## 7:00 – 10:30 · Act 2 — the producer changes things (additive)

**Drift first (60 s).** Tab 5: run `01_land_batch` with batch=2. Back in the pipeline: *Run pipeline* (incremental).
Bronze shows a **`no_undeclared_fields` warning**. `contract_checks` → "Producer drift" cell: rows carry `{"dg_class": "9"}`.
> "The producer started sending dangerous-goods classes. We saw it the same day — not when a consumer complained.
> And the pipeline did not silently invent a column."

**Contract v1.1.0 (45 s).** Run `02_publish_contract_version` (v1.1.0), then show the **Git diff** of the contract:
new optional `dg_class` with a pattern, a reworded description, version 1.1.0.

**Prompt (same chat or new chat):**

```
@contract-driven-pipeline The data contract changed. Update the pipeline.
```

Expected: `diff` → **ADDITIVE** (new optional column, metadata change; semver OK) → minimal edit → check PASS →
summary: *full refresh needed: yes* (column added to streaming tables; replays batch 2 so `dg_class` is backfilled).

**Review (30 s)** — Git diff of `cargo_shipments.py`: **~7 changed lines** (version ×2, bronze schema, silver column + comment,
one new rule, one cast). Compare with `expected_output/v1.1.0`.
> "That's the whole maintenance task. The diff is small because the skill says 'minimal edit'."

**Run** — *Full refresh all*. Result: **silver 617, quarantine 50** — 39 rows now carry `dg_class`; two with the invalid class `3.9`
are in quarantine with `dg_class_format`. Bronze warning gone. Run governance again → `dangerous_goods` tag on `dg_class`, `contract_version=1.1.0`.

## 10:30 – 12:00 · Act 3 — breaking change: the agent stops

Run `02_publish_contract_version` with **v2.0.0** (renames `weight_kg` → `gross_weight_kg`, drops `commodity_description`,
makes `shipper_country` required).

```
@contract-driven-pipeline The data contract changed. Update the pipeline.
```

Expected: **⛔ BREAKING CONTRACT CHANGE — not applied**, table of four changes (incl. "possible rename"), three options
(deprecation period / versioned table `silver_cargo_shipments_v2` / owner sign-off). Show Git: **no files changed**.
> "This is the most important output of the whole demo: the agent saying no."

**Bonus if time (30 s):** publish `v1.2.0-mislabelled` — same breaking change sold as a minor version. Agent reports a **semver violation**.

Reset the contract afterwards (`02_publish_contract_version` → v1.1.0) if you want to show anything else.

## 12:00 – 16:00 · Guardrails, limits, role (slides)

- Guardrails: declarative expectations · UC comments/tags/properties from the contract · deterministic tools + self-check · breaking-change stop · human review via Git.
- **Genie ZeroOps** (private preview) as the operational counterpart: diagnoses failed runs and proposes fixes — still for approval. Talking point only, no live demo.
- Limits seen in practice: non-deterministic form, context and token limits on large contracts/skills, review effort shifts to the engineer.
  (Background: we used Genie Code skills during a production platform migration on Databricks.)
- Role shift: from writing transformation code → owning specifications, encoding standards, reviewing agent output.

## 16:00 – 20:00 · Q&A

Likely questions:
- *"Why not generate the code with a script entirely?"* — Contracts vary (multiple objects, odd sources, edge cases); the agent handles the variance, the tools pin down what must not vary.
- *"What if the agent ignores the skill?"* — `check` fails; the skill forbids handing over failing code; the reviewer sees FAIL.
- *"Where do consumers' contracts fit?"* — Gold tables get their own contracts; same skill pattern, different reference.
- *"Cost?"* — Agent time per change is minutes; the expensive part, the review, gets smaller because the diff is small and standardised.

## If something goes wrong

| Symptom | Do this |
|---|---|
| Agent doesn't pick up the skill | It's `@`-mentioned in the prompt; if still not loaded: new chat, hard-refresh the tab. |
| Agent can't run notebook cells | Run the cells in `explorations/contract_checks` yourself — narrate it as "the same tools the agent uses". |
| `deploy` fails (permissions / SDK) | Set `RUN_FALLBACK = True` in `setup/03_…` and run that cell — same code path; or create the pipeline in the UI (README). |
| Agent is slow (> 3 min) | Talk through SKILL.md; if still stuck, switch to the recording for that act. |
| Generated file fails `check` repeatedly | Copy `expected_output/<version>/transformations/cargo_shipments.py` into `transformations/` — "this is what it produced in rehearsal". |
| Pipeline error on full refresh | Show the recording; mention that serverless start-up is the usual culprit. |
| `ALTER STREAMING TABLE … SET TAGS` refused | Missing `APPLY TAG` or a governed-tag policy on that key — show the generated SQL and the table properties instead. |
| Numbers differ from the script | Run `tests/verify_demo_state` for the stage; batch landed twice → reset. |

## Recording checklist (fallback)

Record each act separately (≤ 3 min each), 1080p, cursor highlight on, no audio needed — you narrate live.
Include: the prompt being typed, the agent's tool calls and summary, the diff, the pipeline graph with counts, the tags.
