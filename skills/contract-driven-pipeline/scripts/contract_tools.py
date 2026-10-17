"""
contract_tools — deterministic helpers for the contract-driven-pipeline skill.

The agent writes the pipeline; this module makes the parts that must never vary
deterministic and checks the agent's output against the contract.

Commands (CLI or import):
  validate     <contract.yaml>                      contract is well-formed + meets team profile
  expectations <contract.yaml>                      rules the pipeline must enforce (derived + custom)
  diff         <old.yaml> <new.yaml>                classify changes: METADATA / ADDITIVE / BREAKING
  governance   <contract.yaml> [--out FILE]         Unity Catalog tags notebook (SQL)
  check        <contract.yaml> <pipeline.py> [--governance FILE]
                                                    generated code matches the contract + conventions

Exit code 0 = OK, 1 = findings that block (errors / breaking change), 2 = usage error.

In a Databricks notebook:
  import sys; sys.path.insert(0, "<skill folder>/scripts")
  import contract_tools as ct
  ct.main(["validate", "/Workspace/.../contracts/cargo_shipments.odcs.yaml"])
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML missing: run %pip install pyyaml")

# --------------------------------------------------------------------------- #
# Team profile (what our contracts must contain on top of ODCS v3)
# --------------------------------------------------------------------------- #
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"]  # ordered by sensitivity
SEVERITIES = {"warning", "error", "critical"}
LOGICAL_TYPES = {"string", "integer", "number", "boolean", "date", "timestamp"}
PHYSICAL_TYPE = re.compile(r"^(STRING|INT|BIGINT|SMALLINT|BOOLEAN|DATE|TIMESTAMP|DOUBLE|DECIMAL\(\d+,\d+\))$")
AUDIT_COLUMNS = [
    ("_ingest_ts", "TIMESTAMP", "Time the record was ingested by the pipeline."),
    ("_source_file", "STRING", "Landing file the record was read from."),
    ("_contract_version", "STRING", "Data contract version the record was validated against."),
]
BRONZE_EXPECTATIONS = {"no_undeclared_fields": "_rescued_data IS NULL"}


@dataclass
class Finding:
    level: str  # ERROR | WARNING
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


def load_contract(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _objects(c: dict) -> list[dict]:
    return c.get("schema") or []


def _server(c: dict) -> dict:
    for s in c.get("servers") or []:
        if s.get("type") == "databricks":
            return s
    return {}


def _custom(c: dict, key: str, default=None):
    for p in c.get("customProperties") or []:
        if p.get("property") == key:
            return p.get("value")
    return default


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #
def validate_contract(c: dict) -> list[Finding]:
    f: list[Finding] = []
    E = lambda w, m: f.append(Finding("ERROR", w, m))
    W = lambda w, m: f.append(Finding("WARNING", w, m))

    if not str(c.get("apiVersion", "")).startswith("v3"):
        E("apiVersion", "must be an ODCS v3 contract (apiVersion: v3.x.y)")
    if c.get("kind") != "DataContract":
        E("kind", "must be DataContract")
    for k in ("id", "name", "version", "status", "domain"):
        if not c.get(k):
            E(k, "is required")
    if c.get("version") and not SEMVER.match(str(c["version"])):
        E("version", f"'{c['version']}' is not semantic versioning (MAJOR.MINOR.PATCH)")
    if c.get("status") not in (None, "active", "draft", "proposed", "deprecated", "retired"):
        W("status", f"unusual status '{c.get('status')}'")
    srv = _server(c)
    if not srv.get("catalog") or not srv.get("schema"):
        E("servers", "needs a databricks server with catalog and schema (the pipeline target)")
    if not _custom(c, "sourcePathConf"):
        E("customProperties", "sourcePathConf (pipeline config key of the landing path) is required")
    if not c.get("team"):
        W("team", "no owner listed")

    objs = _objects(c)
    if not objs:
        E("schema", "at least one schema object is required")
    for o in objs:
        on = o.get("name", "?")
        w = f"schema.{on}"
        if not SNAKE.match(on):
            E(w, "object name must be snake_case")
        if o.get("physicalName") != f"silver_{on}":
            E(w, f"physicalName must be 'silver_{on}' (team naming convention)")
        if not o.get("description"):
            E(w, "description is required (becomes the table comment)")
        for t in o.get("tags") or []:
            if not re.match(r"^[a-z0-9_]+$", str(t)):
                E(w, f"tag '{t}' must be lowercase [a-z0-9_] (Unity Catalog tag key)")
        props = o.get("properties") or []
        names = [p.get("name") for p in props]
        for dup in {n for n in names if names.count(n) > 1}:
            E(w, f"duplicate property '{dup}'")
        if not any(p.get("primaryKey") for p in props):
            W(w, "no primaryKey declared")
        for p in props:
            pn = p.get("name", "?")
            pw = f"{w}.{pn}"
            if not SNAKE.match(pn) or pn.startswith("_"):
                E(pw, "property name must be snake_case and must not start with '_' (reserved for audit columns)")
            if p.get("logicalType") not in LOGICAL_TYPES:
                E(pw, f"logicalType '{p.get('logicalType')}' not in {sorted(LOGICAL_TYPES)}")
            if not PHYSICAL_TYPE.match(str(p.get("physicalType", ""))):
                E(pw, f"physicalType '{p.get('physicalType')}' not supported by the team profile")
            if p.get("classification") not in CLASSIFICATIONS:
                E(pw, f"classification must be one of {CLASSIFICATIONS}")
            if not p.get("description"):
                E(pw, "description is required (becomes the column comment)")
            if p.get("primaryKey") and not p.get("required"):
                E(pw, "primary key columns must be required")
            for t in p.get("tags") or []:
                if not re.match(r"^[a-z0-9_]+$", str(t)):
                    E(pw, f"tag '{t}' must be lowercase [a-z0-9_] (Unity Catalog tag key)")
            if p.get("classification") in ("confidential", "restricted") and "pii" not in (p.get("tags") or []):
                W(pw, "confidential/restricted column without 'pii' tag — confirm with data owner")
            opts = p.get("logicalTypeOptions") or {}
            if "pattern" in opts:
                try:
                    re.compile(opts["pattern"])
                except re.error as ex:
                    E(pw, f"invalid pattern: {ex}")
                if "\\" in opts["pattern"]:
                    W(pw, "pattern uses backslashes; prefer character classes ([0-9], [.]) to avoid SQL escaping issues")
        rnames = []
        for q in o.get("quality") or []:
            qn = q.get("name", "?")
            qw = f"{w}.quality.{qn}"
            rnames.append(qn)
            if not SNAKE.match(qn):
                E(qw, "rule name must be snake_case")
            if q.get("severity") not in SEVERITIES:
                E(qw, f"severity must be one of {sorted(SEVERITIES)}")
            if q.get("type") != "custom" or q.get("engine") != "sql-predicate" or not q.get("implementation"):
                E(qw, "team profile supports type: custom, engine: sql-predicate, implementation: <SQL boolean>")
            if not q.get("description"):
                W(qw, "description missing")
            if re.search(r"(?<!try_)\bCAST\s*\(", str(q.get("implementation", "")), re.I):
                E(qw, "use try_cast, not CAST: under ANSI mode a malformed value would fail the whole pipeline update")
        derived = {r.name for r in derive_rules(o) if r.origin != "quality"}
        for clash in derived.intersection(rnames):
            E(w, f"quality rule '{clash}' clashes with a derived rule name")
        for dup in {n for n in rnames if rnames.count(n) > 1}:
            E(w, f"duplicate quality rule '{dup}'")
    return f


# --------------------------------------------------------------------------- #
# expectations
# --------------------------------------------------------------------------- #
@dataclass
class Rule:
    name: str
    predicate: str
    severity: str  # warning | error | critical
    origin: str    # e.g. "required", "pattern", "quality"
    columns: list[str] = field(default_factory=list)


def _sql_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def derive_rules(o: dict) -> list[Rule]:
    """Rules implied by column definitions + the contract's custom quality rules.

    Derived predicates are NULL-safe (they evaluate to TRUE/FALSE, never NULL).
    Custom predicates are wrapped in coalesce(..., FALSE) so NULL counts as a violation.
    """
    rules: list[Rule] = []
    for p in o.get("properties") or []:
        n = p["name"]
        if p.get("required"):
            rules.append(Rule(f"{n}_not_null", f"{n} IS NOT NULL", "error", "required", [n]))
        opts = p.get("logicalTypeOptions") or {}
        if "pattern" in opts:
            rules.append(Rule(f"{n}_format", f"{n} IS NULL OR {n} RLIKE {_sql_str(opts['pattern'])}",
                              "error", "pattern", [n]))
        bounds = []
        if "minimum" in opts:
            bounds.append(f"{n} >= {opts['minimum']}")
        if "exclusiveMinimum" in opts:
            bounds.append(f"{n} > {opts['exclusiveMinimum']}")
        if "maximum" in opts:
            bounds.append(f"{n} <= {opts['maximum']}")
        if "exclusiveMaximum" in opts:
            bounds.append(f"{n} < {opts['exclusiveMaximum']}")
        if bounds:
            rules.append(Rule(f"{n}_range", f"{n} IS NULL OR ({' AND '.join(bounds)})", "error", "range", [n]))
    prop_names = [p["name"] for p in o.get("properties") or []]
    for q in o.get("quality") or []:
        impl = " ".join(str(q.get("implementation", "")).split())
        cols = [c for c in prop_names if re.search(rf"\b{re.escape(c)}\b", impl)]
        rules.append(Rule(q["name"], f"coalesce(({impl}), FALSE)", q.get("severity", "error"), "quality", cols))
    return rules


def rules_by_severity(o: dict) -> dict[str, dict[str, str]]:
    out = {"critical": {}, "error": {}, "warning": {}}
    for r in derive_rules(o):
        out[r.severity][r.name] = r.predicate
    return out


def silver_schema_ddl(c: dict, o: dict) -> str:
    lines = []
    for p in o.get("properties") or []:
        lines.append(f"{p['name']} {p['physicalType']} COMMENT {_sql_str(' '.join(p['description'].split()))}")
    for n, t, d in AUDIT_COLUMNS:
        lines.append(f"{n} {t} COMMENT {_sql_str(d)}")
    return ",\n".join(lines)


def bronze_schema_ddl(o: dict) -> str:
    return ", ".join(f"{p['name']} STRING" for p in o.get("properties") or [])


def table_properties(c: dict, layer: str) -> dict[str, str]:
    return {
        "quality": layer,
        "contract.id": str(c["id"]),
        "contract.name": str(c["name"]),
        "contract.version": str(c["version"]),
    }


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #
_WIDENING = {("INT", "BIGINT"), ("SMALLINT", "INT"), ("SMALLINT", "BIGINT"), ("INT", "DOUBLE")}


def _is_widening(old: str, new: str) -> bool:
    if (old, new) in _WIDENING:
        return True
    mo, mn = re.match(r"DECIMAL\((\d+),(\d+)\)", old), re.match(r"DECIMAL\((\d+),(\d+)\)", new)
    if mo and mn:
        po, so = map(int, mo.groups())
        pn, sn = map(int, mn.groups())
        return sn >= so and (pn - sn) >= (po - so)
    return False


@dataclass
class Change:
    kind: str  # METADATA | ADDITIVE | BREAKING
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.kind:<9} {self.where}: {self.message}"


def diff_contracts(old: dict, new: dict) -> dict:
    ch: list[Change] = []
    add = lambda k, w, m: ch.append(Change(k, w, m))

    if old.get("id") != new.get("id"):
        add("BREAKING", "id", "contract id changed — this is a different contract")
    so, sn = _server(old), _server(new)
    for k in ("catalog", "schema"):
        if so.get(k) != sn.get(k):
            add("BREAKING", f"servers.{k}", f"target {k} moved {so.get(k)} -> {sn.get(k)}")
    if _custom(old, "sourcePathConf") != _custom(new, "sourcePathConf"):
        add("ADDITIVE", "customProperties.sourcePathConf", "landing path config key changed")
    for k in ("slaProperties", "team", "roles", "description", "status"):
        if old.get(k) != new.get(k):
            add("METADATA", k, "changed")

    oo = {o["name"]: o for o in _objects(old)}
    no = {o["name"]: o for o in _objects(new)}
    for name in oo.keys() - no.keys():
        add("BREAKING", f"schema.{name}", "object removed")
    for name in no.keys() - oo.keys():
        add("ADDITIVE", f"schema.{name}", "new object")
    for name in oo.keys() & no.keys():
        a, b = oo[name], no[name]
        w = f"schema.{name}"
        if a.get("physicalName") != b.get("physicalName"):
            add("BREAKING", w, f"physicalName {a.get('physicalName')} -> {b.get('physicalName')}")
        for k in ("description", "businessName", "tags", "dataGranularityDescription"):
            if a.get(k) != b.get(k):
                add("METADATA", f"{w}.{k}", "changed")
        pa = {p["name"]: p for p in a.get("properties") or []}
        pb = {p["name"]: p for p in b.get("properties") or []}
        removed, added = pa.keys() - pb.keys(), pb.keys() - pa.keys()
        for n in sorted(removed):
            hint = ""
            same_type = [m for m in added if pb[m].get("physicalType") == pa[n].get("physicalType")]
            if same_type:
                hint = f" (possible rename to {', '.join(sorted(same_type))})"
            add("BREAKING", f"{w}.{n}", f"column removed{hint} — consumers reading it will break")
        for n in sorted(added):
            if pb[n].get("required"):
                add("BREAKING", f"{w}.{n}", "new REQUIRED column — existing data and producers do not provide it")
            else:
                add("ADDITIVE", f"{w}.{n}", f"new optional column {pb[n].get('physicalType')}")
        for n in sorted(pa.keys() & pb.keys()):
            x, y = pa[n], pb[n]
            pw = f"{w}.{n}"
            if x.get("physicalType") != y.get("physicalType"):
                if _is_widening(str(x.get("physicalType")), str(y.get("physicalType"))):
                    add("ADDITIVE", pw, f"type widened {x.get('physicalType')} -> {y.get('physicalType')}")
                else:
                    add("BREAKING", pw, f"type changed {x.get('physicalType')} -> {y.get('physicalType')}")
            if bool(x.get("required")) != bool(y.get("required")):
                add("BREAKING", pw, f"required {bool(x.get('required'))} -> {bool(y.get('required'))}")
            if bool(x.get("primaryKey")) != bool(y.get("primaryKey")) or x.get("primaryKeyPosition") != y.get("primaryKeyPosition"):
                add("BREAKING", pw, "primary key changed")
            if (x.get("logicalTypeOptions") or {}) != (y.get("logicalTypeOptions") or {}):
                add("BREAKING", pw, f"validation changed {x.get('logicalTypeOptions')} -> {y.get('logicalTypeOptions')} (accepted rows change)")
            cx, cy = x.get("classification"), y.get("classification")
            if cx != cy:
                if cx in CLASSIFICATIONS and cy in CLASSIFICATIONS and CLASSIFICATIONS.index(cy) > CLASSIFICATIONS.index(cx):
                    add("ADDITIVE", pw, f"classification raised {cx} -> {cy} (governance tags update)")
                else:
                    add("BREAKING", pw, f"classification lowered {cx} -> {cy} — needs data owner sign-off")
            for k in ("description", "businessName", "tags", "examples"):
                if x.get(k) != y.get(k):
                    add("METADATA", f"{pw}.{k}", "changed")
        qa = {q["name"]: q for q in a.get("quality") or []}
        qb = {q["name"]: q for q in b.get("quality") or []}
        for n in sorted(qa.keys() - qb.keys()):
            add("BREAKING", f"{w}.quality.{n}", "rule removed — a guarantee consumers rely on disappears")
        for n in sorted(qb.keys() - qa.keys()):
            q = qb[n]
            cols = [c for c in pb if re.search(rf"\b{re.escape(c)}\b", str(q.get("implementation", "")))]
            only_new = bool(cols) and all(c in added for c in cols)
            if q.get("severity") == "warning" or only_new:
                add("ADDITIVE", f"{w}.quality.{n}", f"new {q.get('severity')} rule" + (" on new columns" if only_new else ""))
            else:
                add("BREAKING", f"{w}.quality.{n}", f"new {q.get('severity')} rule on existing columns — rows accepted today may be dropped")
        for n in sorted(qa.keys() & qb.keys()):
            x, y = qa[n], qb[n]
            if " ".join(str(x.get("implementation")).split()) != " ".join(str(y.get("implementation")).split()):
                add("BREAKING", f"{w}.quality.{n}", "rule logic changed")
            if x.get("severity") != y.get("severity"):
                add("BREAKING" if y.get("severity") in ("error", "critical") else "ADDITIVE",
                    f"{w}.quality.{n}", f"severity {x.get('severity')} -> {y.get('severity')}")

    kinds = {c.kind for c in ch}
    overall = "BREAKING" if "BREAKING" in kinds else "ADDITIVE" if "ADDITIVE" in kinds else "METADATA" if ch else "NONE"
    required_bump = {"BREAKING": "major", "ADDITIVE": "minor", "METADATA": "patch", "NONE": "none"}[overall]
    actual_bump = _bump(str(old.get("version")), str(new.get("version")))
    order = ["none", "patch", "minor", "major"]
    semver_ok = actual_bump != "invalid" and order.index(actual_bump) >= order.index(required_bump)
    return {
        "from": old.get("version"), "to": new.get("version"),
        "overall": overall, "required_bump": required_bump, "actual_bump": actual_bump,
        "semver_ok": semver_ok,
        "changes": [asdict(c) for c in ch],
        "_changes": ch,
    }


def _bump(a: str, b: str) -> str:
    ma, mb = SEMVER.match(a), SEMVER.match(b)
    if not (ma and mb):
        return "invalid"
    x, y = tuple(map(int, ma.groups())), tuple(map(int, mb.groups()))
    if y <= x:
        return "none" if y == x else "invalid"
    return "major" if y[0] > x[0] else "minor" if y[1] > x[1] else "patch"


# --------------------------------------------------------------------------- #
# governance
# --------------------------------------------------------------------------- #
def governance_sql(c: dict) -> str:
    srv = _server(c)
    cat, sch = srv["catalog"], srv["schema"]
    out = [
        "-- Databricks notebook source",
        f"-- GENERATED FROM DATA CONTRACT {c['name']} v{c['version']} by contract_tools.py — DO NOT EDIT BY HAND",
        "-- Applies Unity Catalog tags derived from the contract. Run after the pipeline update",
        "-- (tags cannot be set from inside pipeline code). Column comments come from the pipeline schema.",
        "",
    ]
    for o in _objects(c):
        silver = f"{cat}.{sch}.{o['physicalName']}"
        quarantine = f"{cat}.{sch}.silver_{o['name']}_quarantine"
        table_tags = {
            "contract_id": c["id"], "contract_version": c["version"], "domain": c.get("domain", ""),
            "data_product": c.get("dataProduct", ""), "quality": "silver",
        }
        for t in o.get("tags") or []:
            table_tags[t] = "true"
        max_cls = max((p.get("classification", "public") for p in o.get("properties") or []),
                      key=CLASSIFICATIONS.index, default="public")
        table_tags["classification"] = max_cls

        def stmt(target: str, tags: dict, col: str | None = None) -> str:
            kv = ", ".join(f"{_sql_str(k)} = {_sql_str(str(v))}" for k, v in tags.items())
            alter = f"ALTER COLUMN {col} " if col else ""
            return f"ALTER STREAMING TABLE {target} {alter}SET TAGS ({kv});"

        out += ["-- COMMAND ----------", "", f"-- table: {o['physicalName']}", stmt(silver, table_tags), ""]
        out += ["-- COMMAND ----------", "", "-- columns"]
        for p in o.get("properties") or []:
            tags = {"classification": p.get("classification", "public")}
            for t in p.get("tags") or []:
                tags[t] = "true"
            out.append(stmt(silver, tags, p["name"]))
        out += ["", "-- COMMAND ----------", "", "-- quarantine inherits the most sensitive classification",
                stmt(quarantine, {"contract_id": c["id"], "contract_version": c["version"],
                                  "quality": "quarantine", "classification": max_cls}), ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# check (static review of generated pipeline code)
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return " ".join(str(s).split())


def _assignments(tree: ast.AST) -> dict[str, object]:
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                # allow constants that reference earlier constants, e.g. {"contract.version": CONTRACT_VERSION}
                safe = all(isinstance(n, (ast.Dict, ast.Constant, ast.Name, ast.Load, ast.JoinedStr,
                                          ast.FormattedValue, ast.List, ast.Tuple)) for n in ast.walk(node.value))
                names_known = all(n.id in found for n in ast.walk(node.value) if isinstance(n, ast.Name))
                if safe and names_known:
                    found[node.targets[0].id] = eval(compile(ast.Expression(node.value), "<const>", "eval"),
                                                     {"__builtins__": {}}, dict(found))
                else:
                    found[node.targets[0].id] = ast.unparse(node.value)
    return found


def _decorated_tables(tree: ast.AST) -> dict[str, list[str]]:
    """table name -> list of decorator source strings."""
    tables = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            decs = [ast.unparse(d) for d in node.decorator_list]
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and ast.unparse(d.func) in ("dp.table", "dp.materialized_view"):
                    name = node.name
                    for kw in d.keywords:
                        if kw.arg == "name":
                            try:
                                name = ast.literal_eval(kw.value)
                            except Exception:
                                name = ast.unparse(kw.value)
                    tables[name] = decs
    return tables


def _parse_ddl(ddl: str) -> list[tuple[str, str, str | None]]:
    cols = []
    for line in [l.strip().rstrip(",") for l in str(ddl).splitlines() if l.strip()]:
        m = re.match(r"^(\w+)\s+([A-Z]+(?:\(\d+,\s*\d+\))?)(?:\s+COMMENT\s+'((?:[^'\\]|\\.)*)')?$", line, re.I)
        if not m:
            cols.append((line, "?", None))
        else:
            cols.append((m.group(1), m.group(2).upper().replace(" ", ""), m.group(3)))
    return cols


def check_pipeline(c: dict, pipeline_path: str | Path, governance_path: str | Path | None = None) -> list[Finding]:
    f: list[Finding] = []
    E = lambda w, m: f.append(Finding("ERROR", w, m))
    W = lambda w, m: f.append(Finding("WARNING", w, m))
    src = Path(pipeline_path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as ex:
        return [Finding("ERROR", "syntax", str(ex))]
    a = _assignments(tree)
    tables = _decorated_tables(tree)

    head = "\n".join(src.splitlines()[:12])
    if "GENERATED FROM DATA CONTRACT" not in head or str(c["version"]) not in head or str(c["id"]) not in head:
        E("header", "first lines must carry 'GENERATED FROM DATA CONTRACT', contract id and version")
    if "from pyspark import pipelines as dp" not in src:
        E("imports", "use 'from pyspark import pipelines as dp' (team standard; no legacy 'import dlt')")
    if re.search(r"""['"](/Volumes/|abfss://|dbfs:/|s3://)""", src):
        E("paths", "hard-coded storage path; read it from the pipeline configuration")
    conf_key = _custom(c, "sourcePathConf")
    if conf_key and conf_key not in src:
        E("config", f"landing path must come from spark.conf.get('{conf_key}')")
    for bad in ("collect(", ".count()", "toPandas(", "saveAsTable(", ".start()", "spark.sql(\"ALTER"):
        if bad in src:
            E("dataset code", f"'{bad}' is not allowed inside pipeline code")
    if a.get("CONTRACT_VERSION") != str(c["version"]):
        E("CONTRACT_VERSION", f"is {a.get('CONTRACT_VERSION')!r}, contract says {c['version']!r}")
    if a.get("CONTRACT_ID") != str(c["id"]):
        E("CONTRACT_ID", f"is {a.get('CONTRACT_ID')!r}, contract says {c['id']!r}")

    for o in _objects(c):
        ent = o["name"]
        bronze, silver, quar = f"bronze_{ent}", o["physicalName"], f"silver_{ent}_quarantine"
        for t in (bronze, silver, quar):
            if t not in tables:
                E("tables", f"missing dataset '{t}' (layering convention: bronze -> silver + quarantine)")
        extra = set(tables) - {bronze, silver, quar}
        if extra:
            W("tables", f"datasets not described by the contract/conventions: {sorted(extra)}")

        # bronze schema
        exp_bronze = [p["name"] for p in o["properties"]]
        got_bronze = [x.strip().split()[0] for x in str(a.get("BRONZE_SCHEMA", "")).split(",") if x.strip()]
        if got_bronze != exp_bronze:
            E("BRONZE_SCHEMA", f"columns {got_bronze} != contract {exp_bronze} (all STRING, contract order)")
        if "STRING" not in str(a.get("BRONZE_SCHEMA", "")).upper() or re.search(r"\b(INT|DECIMAL|TIMESTAMP)\b", str(a.get("BRONZE_SCHEMA", "")).upper()):
            E("BRONZE_SCHEMA", "bronze must land every field as STRING; typing happens in silver")
        if "rescuedDataColumn" not in src:
            E("bronze", "Auto Loader must set rescuedDataColumn='_rescued_data' so undeclared fields are visible")
        if a.get("BRONZE_EXPECTATIONS") != BRONZE_EXPECTATIONS:
            E("BRONZE_EXPECTATIONS", f"must be exactly {BRONZE_EXPECTATIONS}")

        # silver schema
        exp_cols = [(p["name"], p["physicalType"].replace(" ", "").upper()) for p in o["properties"]] + \
                   [(n, t) for n, t, _ in AUDIT_COLUMNS]
        got = _parse_ddl(a.get("SILVER_SCHEMA", ""))
        got_cols = [(n, t) for n, t, _ in got]
        if got_cols != exp_cols:
            missing = [x for x in exp_cols if x not in got_cols]
            unexpected = [x for x in got_cols if x not in exp_cols]
            E("SILVER_SCHEMA", f"columns/types differ from contract. missing={missing} unexpected={unexpected}"
              + ("" if missing or unexpected else " (order differs)"))
        descs = {p["name"]: _norm(p["description"]) for p in o["properties"]}
        for n, _, cm in got:
            if n in descs and _norm((cm or "").replace("\\'", "'")) != descs[n]:
                E(f"SILVER_SCHEMA.{n}", "COMMENT must equal the contract description")
        if "try_cast" not in src:
            E("silver", "cast with try_cast so bad values become rule violations, not pipeline failures")

        # expectations
        sev = rules_by_severity(o)
        for var, key in (("ERROR_RULES", "error"), ("WARNING_RULES", "warning"), ("CRITICAL_RULES", "critical")):
            got_r = a.get(var, {} if key == "critical" else None)
            if not isinstance(got_r, dict):
                E(var, "must be a dict literal {rule_name: sql_predicate}")
                continue
            exp_r = sev[key]
            if set(got_r) != set(exp_r):
                E(var, f"rules differ. missing={sorted(set(exp_r) - set(got_r))} unexpected={sorted(set(got_r) - set(exp_r))}")
            for n in set(got_r) & set(exp_r):
                if _norm(got_r[n]) != _norm(exp_r[n]):
                    E(f"{var}.{n}", f"predicate differs from contract:\n      expected: {exp_r[n]}\n      found:    {got_r[n]}")
        sd = " ".join(tables.get(silver, []))
        if "expect_all_or_drop(ERROR_RULES)" not in sd:
            E(silver, "must be decorated with @dp.expect_all_or_drop(ERROR_RULES)")
        if "expect_all(WARNING_RULES)" not in sd:
            E(silver, "must be decorated with @dp.expect_all(WARNING_RULES)")
        if sev["critical"] and "expect_all_or_fail(CRITICAL_RULES)" not in sd:
            E(silver, "must be decorated with @dp.expect_all_or_fail(CRITICAL_RULES)")
        if "expect_all(BRONZE_EXPECTATIONS)" not in " ".join(tables.get(bronze, [])):
            E(bronze, "must be decorated with @dp.expect_all(BRONZE_EXPECTATIONS)")
        if "_failed_rules" not in src:
            E(quar, "quarantine must record _failed_rules")

        # table properties
        tp = a.get("TABLE_PROPERTIES")
        exp_tp = {k: v for k, v in table_properties(c, "silver").items() if k != "quality"}
        if not isinstance(tp, dict) or any(tp.get(k) != v for k, v in exp_tp.items()):
            E("TABLE_PROPERTIES", f"must contain {exp_tp}")

    if governance_path:
        gp = Path(governance_path)
        if not gp.exists():
            E("governance", f"{gp} not found — run: contract_tools.py governance <contract> --out {gp}")
        elif _norm(gp.read_text(encoding="utf-8")) != _norm(governance_sql(c)):
            E("governance", "governance notebook is stale or hand-edited — regenerate it with the governance command")
    return f


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_findings(findings: list[Finding], ok_msg: str) -> int:
    errs = [x for x in findings if x.level == "ERROR"]
    for x in findings:
        print(x)
    print(("FAIL" if errs else "PASS") + f" — {len(errs)} error(s), {len(findings) - len(errs)} warning(s)."
          + ("" if errs else f" {ok_msg}"))
    return 1 if errs else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [x for x in argv if x != "--json"]
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]

    def opt(name):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return v
        return None

    if cmd == "validate" and len(args) == 1:
        c = load_contract(args[0])
        print(f"Contract {c.get('name')} v{c.get('version')} ({args[0]})")
        return _print_findings(validate_contract(c), "Contract is valid.")

    if cmd == "expectations" and len(args) == 1:
        c = load_contract(args[0])
        out = []
        for o in _objects(c):
            for r in derive_rules(o):
                out.append(asdict(r))
        if as_json:
            print(json.dumps(out, indent=2))
        else:
            mode = {"error": "drop + quarantine", "warning": "keep, track", "critical": "fail update"}
            print(f"{'rule':<34} {'severity':<9} {'action':<18} predicate")
            for r in out:
                print(f"{r['name']:<34} {r['severity']:<9} {mode[r['severity']]:<18} {r['predicate']}")
        return 0

    if cmd == "diff" and len(args) == 2:
        d = diff_contracts(load_contract(args[0]), load_contract(args[1]))
        if as_json:
            print(json.dumps({k: v for k, v in d.items() if not k.startswith("_")}, indent=2))
        else:
            print(f"Contract diff {d['from']} -> {d['to']}")
            for x in d["_changes"]:
                print("  " + str(x))
            print(f"Overall: {d['overall']} | required bump: {d['required_bump']} | actual bump: {d['actual_bump']}"
                  f" | semver {'OK' if d['semver_ok'] else 'VIOLATION'}")
            if d["overall"] == "BREAKING" or not d["semver_ok"]:
                print("STOP: do not modify the pipeline. Report these changes to a human for a decision.")
            else:
                print("OK to apply: changes are additive/metadata only.")
        return 1 if d["overall"] == "BREAKING" or not d["semver_ok"] else 0

    if cmd == "governance" and len(args) in (1, 3):
        out_path = opt("--out")
        sql = governance_sql(load_contract(args[0]))
        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_text(sql, encoding="utf-8")
            print(f"Wrote {out_path}")
        else:
            print(sql)
        return 0

    if cmd == "check" and len(args) in (2, 4):
        gov = opt("--governance")
        c = load_contract(args[0])
        print(f"Checking {args[1]} against {c['name']} v{c['version']}")
        return _print_findings(check_pipeline(c, args[1], gov), "Pipeline matches the contract and team conventions.")

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
