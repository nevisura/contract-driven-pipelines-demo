---
name: excel-to-data-contract
description: Create or update an ODCS v3 data contract YAML from an Excel specification (Contract / Columns / Quality / Team / Roles sheets), with validation and automatic semantic versioning. Use when asked to turn an Excel, spreadsheet, data dictionary or spec into a data contract, to regenerate a contract after the Excel changed, or to produce a blank contract template.
---

# Excel → data contract

Business analysts and data owners describe a dataset in Excel; you turn that workbook into the
versioned data contract that the `contract-driven-pipeline` skill builds pipelines from.
**The Excel is the source, the contract is generated.** You never invent content the Excel doesn't
contain, and you never publish a breaking contract change without the data owner's explicit sign-off.

| File | Use it for |
|---|---|
| `mapping.md` | How each sheet/column maps to the contract, accepted values, common fixes |
| `reference/data_contract_template.xlsx` | Blank workbook to hand to the data owner (instructions + dropdowns) |
| `scripts/excel_contract.py` | `convert`, `template`, `from-contract`, `set` — deterministic conversion and versioning |

The script reuses `contract-driven-pipeline/scripts/contract_tools.py` (same validator, same diff), so
that skill must be installed next to this one.

## How to run the tool

In a Python notebook cell (absolute `/Workspace/...` path of this skill folder):

```python
%pip install -q openpyxl pyyaml          # once per session if the import fails
import sys, importlib
SKILL_DIR = "/Workspace/<path to>/skills/excel-to-data-contract"
sys.path.insert(0, f"{SKILL_DIR}/scripts")
import excel_contract as xc; importlib.reload(xc)
xc.main(["convert", "<spec.xlsx>", "<repo>/contracts/<name>.odcs.yaml"])
```

Exit code `0` = written or unchanged, `1` = blocked (nothing written).

## Workflow

### 1. Locate the inputs
- **Excel spec**: the path the user gives, or `specs/<name>.xlsx` in the repo. A workbook in a Volume works too.
- **Output contract**: `contracts/<name>.odcs.yaml` in the repo (`<name>` = the `name` field on the Contract sheet).
  If it exists, it is the **previous version** the change is compared against.

### 2. Dry run first
`xc.main(["convert", SPEC, OUT, "--dry-run"])`. Read every issue:
- **ERROR** lines name the sheet and row/field (e.g. `Columns!row 7`). Do **not** fix the Excel yourself.
  Report them in a table (cell → problem → suggested fix) and ask the owner to correct the workbook.
  Typical fixes are in `mapping.md`.
- **WARNING** lines (derived id, default physical type, default classification) — list them in your
  summary so the owner can confirm or fill them in.
- **INFO** `proposed X.Y.Z` — the version the tool chose from the change type.

### 3. Decide
| Dry-run result | Action |
|---|---|
| `UNCHANGED` | Tell the user the contract already matches the Excel. Stop. |
| `BLOCKED` with Excel errors | Report the cells to fix. Stop. |
| `BLOCKED` — **semver violation** | The Excel's `version` is too small for the change. Say which bump is required; ask the owner to fix or clear the version cell. Stop. |
| `BLOCKED` — **BREAKING** | Show the breaking changes and who is affected. Write **nothing**. Only if the user confirms the data owner's sign-off in the chat, re-run with `--allow-breaking`. |
| Would `create` / `update` | Go to step 4. |

### 4. Write the contract
Run the same command without `--dry-run`. Then validate with the pipeline skill's tool:
`ct.main(["validate", OUT])` (import `contract_tools` from `skills/contract-driven-pipeline/scripts`). It must PASS.

### 5. Hand over
Do not build or change the pipeline in this skill. Reply with:

```
Contract <name> v<version> <created|updated> from <spec.xlsx>   (validate: PASS)
| Change | Kind |
|---|---|
| ... | ADDITIVE / METADATA |
Please confirm: <warnings the owner should check>
Next: @contract-driven-pipeline Build and deploy the pipeline for <contract path>      (new contract)
      @contract-driven-pipeline The data contract <contract path> changed. Update the pipeline.   (update)
```

## Other commands
- **Blank template for a new dataset**: `xc.main(["template", "<out.xlsx>"])` — or copy `reference/data_contract_template.xlsx`.
- **Existing contract → Excel** (onboarding an existing contract to the Excel workflow):
  `xc.main(["from-contract", "<contract.yaml>", "<out.xlsx>"])`.
- **Change one Contract field** (e.g. move to another catalog): `xc.main(["set", "<spec.xlsx>", "catalog", "<value>"])`.

## Edge cases
- **Messy cells** (`Yes`, `X`, `TRUE`, `1.0`, trailing spaces): the tool normalises them; anything ambiguous is an ERROR, not a guess.
- **Column names not snake_case** (`AWB Number`): ERROR with a suggested name — renaming is the owner's decision because consumers see it.
- **Rules using `CAST`**: blocked by validation — suggest `try_cast`.
- **Several datasets in one workbook**: not supported — one workbook per contract.
- **The user asks you to edit the YAML directly**: explain that the Excel is the source and the YAML would be overwritten; offer to change the Excel cell with `set` (Contract fields) or ask them to edit the row.
