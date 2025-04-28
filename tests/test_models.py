from faff.models import Plan
from pathlib import Path
from datetime import date

def test_plan_from_toml_file():
    test_file = Path("tests/testdata/sample_plan.toml")
    plan = Plan.Plan.from_toml_file(test_file)

    assert plan.source == "local"
    assert plan.valid_from == date(2025, 3, 20)
    assert plan.valid_until == date(2025, 4, 1)
    assert len(plan.activities) == 2
    assert plan.activities[0].id == "work:admin"
