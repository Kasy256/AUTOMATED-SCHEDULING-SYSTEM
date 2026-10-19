import ast
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.industry_templates.schemas import (
    IndustryTemplateDefinition,
    TemplateConstraint,
    load_packaged,
)
from support import APP, db_url, fetch, signup_and_confirm, superuser_url

Shape = tuple[str, tuple[tuple[str, object], ...], tuple[str, ...], tuple[tuple[str, object], ...]]

# DOMAIN_MODEL §5 legacy hard rules, plus the confirmed weekly caps (no part-time cap).
EXPECTED_HARD: set[Shape] = {
    ("capacity_fit", (("headcount_from", "group_sizes"),), (), ()),
    ("max_load", (("max_count", 2), ("period", "day")), ("lecturer",), ()),
    ("max_load", (("max_count", 1), ("period", "day"), ("window", "morning")), ("lecturer",), ()),
    ("max_load", (("max_count", 1), ("period", "day"), ("window", "afternoon")), ("lecturer",), ()),
    (
        "max_load",
        (("max_minutes", 1320), ("period", "week")),
        ("lecturer",),
        (("role", "Full-Time"),),
    ),
    (
        "max_load",
        (("max_minutes", 900), ("period", "week")),
        ("lecturer",),
        (("role", "Faculty Dean"),),
    ),
    ("spread", (("max_per_day", 1),), (), ()),
}


def _shape(c: TemplateConstraint) -> Shape:
    params = tuple(sorted((k, v) for k, v in c.params.items() if v is not None))
    attrs = tuple((a.attr, a.value) for a in c.scope.attrs)
    return (c.template_key, params, tuple(c.scope.resource_type_keys), attrs)


def _raw() -> dict[str, Any]:
    text = files("cartlyf_api.industry_templates").joinpath("data/education.json").read_text()
    return json.loads(text)


def test_EDU_02_education_hard_rules_match_the_mapping() -> None:
    template = load_packaged("education")
    assert {_shape(c) for c in template.constraints if c.hard} == EXPECTED_HARD


def test_EDU_02_soft_rules_and_weights() -> None:
    soft = {
        (c.template_key, c.weight) for c in load_packaged("education").constraints if not c.hard
    }
    expected = {("minimize_gaps", 35), ("balance", 30), ("capacity_fit", 20)}
    assert soft == expected | {("day_distribution", 15), ("stability", 100)}


def test_education_v2_repairs_stay_close_to_the_published_plan() -> None:
    template = load_packaged("education")
    (stability,) = [c for c in template.constraints if c.template_key == "stability"]
    assert template.version == 2
    assert stability.params == {"per_change": 1, "per_resource_change": 1}
    assert stability.scope.resource_type_keys == []


def test_EDU_02_periods_come_from_legacy_config() -> None:
    slots = load_packaged("education").slot_templates[0].definition.slots
    starts = [(s.start_minute, s.duration_minutes) for s in slots]
    assert starts == [(540, 120), (660, 120), (840, 120), (960, 120)]
    assert all(s.weekdays == [0, 1, 2, 3, 4] for s in slots)  # Monday is 0


def test_template_params_are_stored_normalised() -> None:
    first = load_packaged("education").constraints[1]
    assert first.params == {"period": "day", "window": None, "max_count": 2, "max_minutes": None}


def test_template_rejects_scope_on_unknown_type() -> None:
    data = _raw()
    data["constraints"][1]["scope"]["resource_type_keys"] = ["nurse"]
    with pytest.raises(ValidationError, match="nurse"):
        IndustryTemplateDefinition.model_validate(data)


def test_template_rejects_invalid_rule_params() -> None:
    data = _raw()
    data["constraints"][1]["params"] = {"period": "day"}
    with pytest.raises(ValidationError, match="max_count"):
        IndustryTemplateDefinition.model_validate(data)


def test_template_rejects_hard_soft_only_rule() -> None:
    data = _raw()
    balance = next(c for c in data["constraints"] if c["template_key"] == "balance")
    balance["hard"] = True
    with pytest.raises(ValidationError, match="only be soft"):
        IndustryTemplateDefinition.model_validate(data)


def test_demand_shape_names_known_types_and_slot_template() -> None:
    data = _raw()
    data["demand_shape"]["slot_template"] = "Nope"
    with pytest.raises(ValidationError, match="Nope"):
        IndustryTemplateDefinition.model_validate(data)


@pytest.mark.integration
def test_EDU_02_migration_seeds_the_packaged_template(migrated_pg: PostgresContainer) -> None:
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT key, version, definition FROM industry_template WHERE key = 'education' "
        "ORDER BY version",
    )
    packaged = load_packaged("education").model_dump(mode="json")
    assert [(k, v) for k, v, _ in rows] == [("education", 1), ("education", 2)]
    assert rows[-1][2] == packaged


@pytest.mark.integration
def test_app_role_can_only_read_templates(migrated_pg: PostgresContainer) -> None:
    app_url = db_url(migrated_pg, *APP)
    assert fetch(app_url, "SELECT count(*) FROM industry_template") == [(3,)]
    with pytest.raises(Exception, match="permission denied"):
        fetch(app_url, "DELETE FROM industry_template RETURNING key")


@pytest.mark.integration
def test_members_list_templates(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    response = client.get("/api/v1/industry-templates", headers=admin.auth)
    assert response.status_code == 200, response.text
    education, healthcare = response.json()
    assert (education["key"], education["version"]) == ("education", 2)
    assert (healthcare["key"], healthcare["version"]) == ("healthcare", 1)
    assert len(education["constraints"]) == 12
    assert client.get("/api/v1/industry-templates").status_code == 401


VERSIONS = Path(__file__).resolve().parents[1] / "migrations/versions"


@pytest.mark.parametrize(
    "migration", ["0005_industry_template.py", "0008_education_v2.py", "0009_healthcare_v1.py"]
)
def test_template_migrations_are_frozen(migration: str) -> None:
    # Migrations never change: they seed frozen copies, never the live file or models.
    tree = ast.parse((VERSIONS / migration).read_text(encoding="utf-8"))
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for name in (
            [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else [a.name for a in node.names]
        )
    }
    assert not any(n.startswith(("cartlyf_api", "cartlyf_engine")) for n in imported), imported


def test_latest_frozen_copy_is_the_packaged_template() -> None:
    frozen = json.loads((VERSIONS / "0008_education_v2.json").read_text(encoding="utf-8"))
    # Editing a seeded version in place would fork fresh and existing databases: bump it.
    assert frozen == load_packaged("education").model_dump(mode="json")


def test_education_v1_copy_is_unchanged() -> None:
    v1 = json.loads((VERSIONS / "0005_education_v1.json").read_text(encoding="utf-8"))
    assert v1["version"] == 1
    assert len(v1["constraints"]) == 11
