"""Checks that the baseline sales_summary model stays valid for the demo."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBT_MODEL = ROOT / "pipeline" / "dbt" / "models" / "marts" / "sales_summary.sql"


def test_model_references_raw_sales_source():
    """The mart must read raw_sales through a dbt source, not a hard-coded table."""
    sql = DBT_MODEL.read_text(encoding="utf-8").lower()
    assert "raw_sales" in sql
    assert "source(" in sql


def test_model_has_demo_tag():
    """The demo tag is how the agent and dbt project identify this model."""
    sql = DBT_MODEL.read_text(encoding="utf-8")
    assert "demo_sales_etl" in sql


def test_no_obvious_syntax_errors():
    """Guard against the missing-comma injection being left in the baseline model."""
    sql = DBT_MODEL.read_text(encoding="utf-8").lower()
    assert "user_id sum(" not in sql.replace(",", "").replace("\n", " ")
