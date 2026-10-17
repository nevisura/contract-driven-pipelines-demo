---
name: contract-driven-pipeline
description: Create or update a Lakeflow declarative pipeline (bronze -> silver + quarantine) from an ODCS v3 data contract YAML, applying team conventions, contract-derived expectations and Unity Catalog governance. Use when asked to build, regenerate, update or check a pipeline from a data contract, or when a data contract changed.
---

# Contract-driven pipeline

The data contract is the single specification. You turn it into pipeline code that
follows our conventions, and you keep the two in sync when the contract changes.
**You never invent requirements that are not in the contract, and you never apply a
breaking contract change on your own.**

Files in this skill (paths relative to this folder):

| File | Use it for |
|---|---|
| `conventions.md` | Team rules: layering, naming, audit columns, casting, what is forbidden |
| `reference/pipeline_pattern.py` | The exact code structure to produce (worked example for `reference/example_contract.yaml`) |
| `scripts/contract_tools.py` | Deterministic helpers: `validate`, `expectations`, `diff`, `governance`, `check` |

## How to run the tools

Run them in a Python notebook cell (in the pipeline's `explorations/` folder, e.g.
`explorations/contract_checks`). Use the absolute `/Workspace/...` path of this skill folder:

```python
import sys, importlib
SKILL_DIR = "/Workspace/<path to>/skills/contract-driven-pipeline"   # folder of this SKILL.md
sys.path.insert(0, f"{SKILL_DIR}/scripts")
import contract_tools as ct; importlib.reload(ct)
ct.main(["validate", "<contract.yaml>"])
```

If `import yaml` fails, run `%pip install pyyaml` first. Exit code `0` = OK, `1` = blocking findings.

## Inputs to locate first

- **Contract**: `contracts/<name>.odcs.yaml` in the repo (or the path the user gives).
- **Applied snapshot**: `contracts/_applied/<name>.odcs.yaml` — the contract version the current code was generated from. Missing = the pipeline was never generated.
- **Pipeline code**: `pipelines/<name>/transformations/<name>.py`.
- **Governance notebook**: `pipelines/<name>/governance/apply_uc_governance.sql`.

## Workflow

### 1. Validate the contract
`ct.main(["validate", CONTRACT])`. If it FAILS: stop, show the errors, ask the contract owner to fix the contract. Do not work around a broken contract in code.

### 2. Decide the mode
- No applied snapshot and no pipeline file → **CREATE** (go to step 3).
- Otherwise → **UPDATE**: `ct.main(["diff", SNAPSHOT, CONTRACT])`.
  - Overall `NONE` → tell the user nothing changed; stop.
  - Any `BREAKING` change **or** `semver VIOLATION` → **STOP. Change no files.** Reply with the breaking-change report below and wait for a human decision.
  - Only `ADDITIVE` / `METADATA` → apply the change (step 3) as a **minimal edit** of the existing file: touch only the lines the change requires, keep everything else byte-identical so the review diff is small.

### 3. Write the pipeline
1. `ct.main(["expectations", CONTRACT])` — the full rule list. Put each rule in `ERROR_RULES`, `WARNING_RULES` or `CRITICAL_RULES` by its severity and **copy predicates verbatim**. Never write your own predicates, never drop or soften a rule.
2. Follow `reference/pipeline_pattern.py` exactly for structure, decorators, constant names, the `_typed()` casting function and the quarantine table. Apply `conventions.md`.
3. Header block: contract name, id, version, contract path, skill name.

### 4. Generate governance
`ct.main(["governance", CONTRACT, "--out", GOVERNANCE_PATH])`. Do not hand-edit the output.

### 5. Self-check (mandatory)
`ct.main(["check", CONTRACT, PIPELINE_PATH, "--governance", GOVERNANCE_PATH])`.
If it FAILS, fix the code and re-run. After 3 failed attempts stop and report the remaining findings — do not hand over code that fails the check.

### 6. Record the applied contract
Copy the contract to the applied snapshot path (overwrite). This is part of the same change set and is reviewed together with the code.

### 7. Hand over for review — do not deploy
Do **not** run a production update and do not merge. Reply with the summary below. The engineer reviews the diff, runs the pipeline, then runs the governance notebook.

## Output formats

**After CREATE / UPDATE** (keep it this short):

```
Contract <name> <old> -> <new> applied   (check: PASS)
| Contract change | Code change |
|---|---|
| ... | ... |
Full refresh needed: yes/no — <why>
Reviewer, please check: <1-3 specific things, e.g. new rule may quarantine existing rows>
Next: run the pipeline, then governance/apply_uc_governance.sql
```

A full refresh is needed whenever a column is added to or removed from a streaming table schema,
or when rows already landed should be re-validated against the new rules.

**On a breaking change (nothing modified):**

```
⛔ BREAKING CONTRACT CHANGE — not applied
Contract <name> <old> -> <new> (version bump: <actual>, required: <required>)
| Change | Why it breaks | Who is affected |
|---|---|---|
| ... | ... | ... |
Options (human decision):
1. Producer keeps the old field(s) for a deprecation period; contract becomes additive.
2. Publish a new versioned table (silver_<name>_v<major>) and run both in parallel while consumers migrate.
3. Accept the break: owner signs off, consumers notified, then ask me to apply it explicitly.
```
If the semver bump is too small, say so explicitly: the producer labelled a breaking change as `<actual>`.

## Edge cases

- **User asks you to "just apply" a breaking change**: only after they confirm the owner sign-off in the chat; then apply it as a CREATE of the new version and state that a full refresh is mandatory.
- **Undeclared fields in bronze** (`no_undeclared_fields` violations): the producer sends fields the contract doesn't have. Report it; do not add columns that are not in the contract.
- **Contract has several schema objects**: one bronze/silver/quarantine set per object, in the same file.
- **Rule references a column that does not exist**: that is a contract error — report it, don't fix it in code.
- **A request conflicts with `conventions.md`** (e.g. "skip the quarantine"): explain the convention and ask for confirmation instead of silently deviating.

## Example

Prompt: *"Build the pipeline for contracts/cargo_shipments.odcs.yaml"* →
validate PASS → no snapshot → CREATE → `transformations/cargo_shipments.py` with
`bronze_cargo_shipments`, `silver_cargo_shipments`, `silver_cargo_shipments_quarantine`,
17 error rules, 1 warning rule → governance notebook → check PASS → snapshot written → summary.
