"""Plain-python regression tests: python tests/test_contract_tools.py (no pytest needed)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/contract-driven-pipeline/scripts"))
import contract_tools as ct  # noqa: E402

V = ROOT / "demo/contract_versions"
c = {v: ct.load_contract(V / f"cargo_shipments.{v}.yaml") for v in ("v1.0.0", "v1.1.0", "v2.0.0", "v1.2.0-mislabelled")}
errors = lambda fs: [f for f in fs if f.level == "ERROR"]

for v, k in c.items():
    assert not errors(ct.validate_contract(k)), v
for v in ("v1.0.0", "v1.1.0"):
    p = ROOT / f"expected_output/{v}/transformations/cargo_shipments.py"
    g = ROOT / f"expected_output/{v}/governance/apply_uc_governance.sql"
    assert not errors(ct.check_pipeline(c[v], p, g)), v
# stale code is detected
assert len(errors(ct.check_pipeline(c["v1.1.0"], ROOT / "expected_output/v1.0.0/transformations/cargo_shipments.py"))) >= 5
# diff classification
d = ct.diff_contracts(c["v1.0.0"], c["v1.1.0"]); assert d["overall"] == "ADDITIVE" and d["semver_ok"]
d = ct.diff_contracts(c["v1.1.0"], c["v2.0.0"]); assert d["overall"] == "BREAKING" and d["semver_ok"]
d = ct.diff_contracts(c["v1.1.0"], c["v1.2.0-mislabelled"]); assert d["overall"] == "BREAKING" and not d["semver_ok"]
# an unsafe CAST in a rule is rejected
bad = ct.load_contract(V / "cargo_shipments.v1.0.0.yaml")
bad["schema"][0]["quality"][1]["implementation"] = "CAST(substr(awb_number, 5, 7) AS BIGINT) > 0"
assert any("try_cast" in f.message for f in errors(ct.validate_contract(bad)))
# skill's own reference example passes
ref = ROOT / "skills/contract-driven-pipeline/reference"
assert not errors(ct.check_pipeline(ct.load_contract(ref / "example_contract.yaml"), ref / "pipeline_pattern.py"))
print("all contract_tools tests passed")
