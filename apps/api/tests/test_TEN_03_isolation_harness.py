from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.examples import example_id
from cartlyf_api.main import create_app
from support import (
    Operation,
    body_id_names,
    build_world,
    make_settings,
    missing_seeds,
    openapi_operations,
    ordered,
    substitute_ids,
    url_for,
)

# Routes that 404 for an ordinary org admin whatever the id, so the positive control below
# cannot apply; each needs its own isolation test (here: test_TEN_06_platform_admin.py).
NOT_FOUND_BY_DESIGN = {"POST /api/v1/platform/organisations/{organisation_id}/session"}


@pytest.mark.integration
def test_TEN_03_other_org_ids_are_not_found_on_every_route(
    client: TestClient, app: FastAPI
) -> None:
    world = build_world(client, app)
    checked: list[str] = []
    for op in ordered(openapi_operations(app)):
        if not op.path_params:
            continue
        route = f"{op.method} {op.path}"
        missing = missing_seeds(op, world.b_ids)
        assert not missing, f"{route}: seed an org-B id for {missing} in build_world"
        response = client.request(
            op.method,
            url_for(op, world.b_ids),
            headers=world.a_admin.auth,
            json=substitute_ids(op.body, world.b_ids),
        )
        assert response.status_code == 404, f"{route} -> {response.status_code}"
        if route not in NOT_FOUND_BY_DESIGN:
            # Positive control: the seeds must name real objects, or the 404 above proves nothing.
            control = client.request(
                op.method,
                url_for(op, world.a_ids),
                headers=world.a_admin.auth,
                json=substitute_ids(op.body, world.a_ids),
            )
            assert control.status_code != 404, f"{route}: own-org seed is not a real object"
        checked.append(route)
    # Guards against the harness silently checking nothing.
    assert len(checked) >= 3, checked


@pytest.mark.integration
def test_TEN_03_other_org_ids_in_bodies_are_not_found(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    checked: list[str] = []
    for op in ordered(openapi_operations(app)):
        # One id at a time, the rest own-org: the first id resolved must not mask the others.
        for name in sorted(body_id_names(op.body)):
            route = f"{op.method} {op.path} [{name}]"
            mixed = {**world.a_ids, name: world.b_ids[name]}
            response = client.request(
                op.method,
                url_for(op, world.a_ids),
                headers=world.a_admin.auth,
                json=substitute_ids(op.body, mixed),
            )
            assert response.status_code == 404, f"{route} with org-B id -> {response.status_code}"
            checked.append(route)
    # Guards against example bodies silently losing their ids.
    assert len(checked) >= 15, checked


@pytest.mark.integration
def test_TEN_03_demand_imports_reject_other_org_ids(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    a, b = world.a_ids, world.b_ids
    create = {"kind": "demands", "schedule_id": b["schedule_id"], "filename": "d.csv"}
    response = client.post("/api/v1/imports", headers=world.a_admin.auth, json=create)
    assert response.status_code == 404
    own = {"kind": "demands", "schedule_id": a["schedule_id"], "filename": "d.csv"}
    job = client.post("/api/v1/imports", headers=world.a_admin.auth, json=own).json()
    upload = client.put(
        f"/api/v1/imports/{job['id']}/file",
        headers=world.a_admin.auth | {"Content-Type": "text/csv"},
        content=b"Course,Sessions\nX,1\n",
    )
    assert upload.status_code == 200
    for slot_template, resource_type in [
        (b["slot_template_id"], a["resource_type_id"]),
        (a["slot_template_id"], b["resource_type_id"]),
    ]:
        mapping = {
            "kind": "demands",
            "demand_kind": "session",
            "slot_template_id": slot_template,
            "name": "Course",
            "sessions_per_week": "Sessions",
            "requirements": [{"role": "lecturer", "resource_type_id": resource_type}],
        }
        response = client.post(
            f"/api/v1/imports/{job['id']}/dry-run",
            headers=world.a_admin.auth,
            json={"mapping": mapping},
        )
        assert response.status_code == 404, response.text


def test_TEN_03_substitutes_example_ids_in_bodies() -> None:
    body = {
        "resource_type_id": example_id("resource_type_id"),
        "nested": [example_id("resource_id")],
    }
    assert body_id_names(body) == {"resource_type_id", "resource_id"}
    swapped = substitute_ids(body, {"resource_type_id": "T", "resource_id": "R"})
    assert swapped == {"resource_type_id": "T", "nested": ["R"]}
    with pytest.raises(AssertionError, match="seed an id for 'resource_id'"):
        substitute_ids(body, {"resource_type_id": "T"})


def test_TEN_03_deletes_run_last_children_first() -> None:
    def op(method: str, path: str) -> Operation:
        return Operation(path, method, [], None)

    ops = [
        op("DELETE", "/api/v1/schedules/{schedule_id}"),
        op("DELETE", "/api/v1/schedules/{schedule_id}/activities/{activity_id}"),
        op("GET", "/api/v1/schedules/{schedule_id}"),
        op("DELETE", "/api/v1/schedules/{schedule_id}/pins/{activity_id}"),
    ]
    assert [(o.method, o.path.rsplit("/", 2)[-2]) for o in ordered(ops)] == [
        ("GET", "schedules"),
        ("DELETE", "pins"),
        ("DELETE", "activities"),
        ("DELETE", "schedules"),
    ]


def test_TEN_03_harness_flags_a_route_without_a_seed() -> None:
    app = create_app(make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0"))

    @app.get("/api/v1/widgets/{widget_id}")
    async def get_widget(widget_id: UUID) -> None:  # pyright: ignore[reportUnusedFunction]
        return None

    probe = next(op for op in openapi_operations(app) if op.path == "/api/v1/widgets/{widget_id}")
    assert missing_seeds(probe, {"membership_id": "x", "organisation_id": "y"}) == {"widget_id"}


def test_TEN_03_harness_requires_body_examples() -> None:
    from pydantic import BaseModel

    class NoExample(BaseModel):
        value: int

    app = create_app(make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0"))

    @app.post("/api/v1/things")
    async def create_thing(body: NoExample) -> None:  # pyright: ignore[reportUnusedFunction]
        return None

    with pytest.raises(AssertionError, match="NoExample: add json_schema_extra examples"):
        openapi_operations(app)
