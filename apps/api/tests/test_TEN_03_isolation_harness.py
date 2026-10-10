from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.main import create_app
from support import build_world, make_settings, missing_seeds, openapi_operations


@pytest.mark.integration
def test_TEN_03_other_org_ids_are_not_found_on_every_route(
    client: TestClient, app: FastAPI
) -> None:
    world = build_world(client, app)
    checked: list[str] = []
    for op in openapi_operations(app):
        if not op.path_params:
            continue
        missing = missing_seeds(op, world.b_ids)
        assert not missing, f"{op.method} {op.path}: seed an org-B id for {missing} in build_world"
        url = op.path.format(**{name: world.b_ids[name] for name in op.path_params})
        response = client.request(op.method, url, headers=world.a_admin.auth, json=op.body)
        assert response.status_code == 404, f"{op.method} {op.path} -> {response.status_code}"
        checked.append(f"{op.method} {op.path}")
    # Guards against the harness silently checking nothing.
    assert len(checked) >= 3, checked


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
