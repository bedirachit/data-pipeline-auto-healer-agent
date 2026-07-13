"""Unit tests for dbt model validation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBT_MODEL = ROOT / "pipeline" / "dbt" / "models" / "marts" / "sales_summary.sql"


def test_model_references_raw_sales_source():
    sql = DBT_MODEL.read_text(encoding="utf-8").lower()
    assert "raw_sales" in sql
    assert "source(" in sql


def test_model_has_demo_tag():
    sql = DBT_MODEL.read_text(encoding="utf-8")
    assert "demo_sales_etl" in sql


def test_no_obvious_syntax_errors():
    sql = DBT_MODEL.read_text(encoding="utf-8").lower()
    assert "user_id sum(" not in sql.replace(",", "").replace("\n", " ")
