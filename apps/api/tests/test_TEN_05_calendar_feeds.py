import hashlib
import re
import secrets
from datetime import UTC, datetime
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import (
    Account,
    add_member,
    build_schedule,
    fetch,
    free_start,
    get_version,
    move,
    publish,
    signup_and_confirm,
    solve_now,
    superuser_url,
)

pytestmark = pytest.mark.integration
URL = re.compile(r"^http://api\.test/api/v1/calendar/([A-Za-z0-9_-]{43})\.ics$")


def _create(client: TestClient, account: Account, resource_id: str) -> dict[str, Any]:
    response = client.post(f"/api/v1/resources/{resource_id}/calendar-feeds", headers=account.auth)
    assert response.status_code == 201, response.text
    return response.json()


def _token(feed: dict[str, Any]) -> str:
    match = URL.match(feed["url"])
    assert match, feed["url"]
    return match.group(1)


def _ics(client: TestClient, token: str) -> httpx.Response:
    return client.get(f"/api/v1/calendar/{token}.ics")


def _events(body: str) -> list[dict[str, str]]:
    unfolded = body.replace("\r\n ", "")
    return [
        dict(line.split(":", 1) for line in block.strip("\r\n").split("\r\n"))
        for block in re.findall(r"BEGIN:VEVENT\r\n(.*?)END:VEVENT", unfolded, re.S)
    ]


def _utc(value: str | datetime) -> str:
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _link(client: TestClient, admin: Account, resource_id: str, member: Account) -> None:
    user_id = client.get("/api/v1/auth/me", headers=member.auth).json()["user_id"]
    response = client.patch(
        f"/api/v1/resources/{resource_id}", headers=admin.auth, json={"user_id": user_id}
    )
    assert response.status_code == 200, response.text


def test_TEN_05_feed_serves_published_assignments(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, lecturers=2, demands=4, sessions=1)
    _, version_id = solve_now(client, admin, built.schedule_id)
    assert publish(client, admin, version_id).status_code == 200
    version = get_version(client, admin, version_id)
    mine = version["assignments"][0]["resources"]["lecturer"][0]
    expected = [a for a in version["assignments"] if mine in a["resources"]["lecturer"]]

    feed = _create(client, admin, mine)
    assert feed["resource_id"] == mine
    response = _ics(client, _token(feed))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert response.headers["cache-control"] == "private, max-age=300"
    events = _events(response.text)
    assert {e["UID"] for e in events} == {f"{a['activity_id']}@cartlyf" for a in expected}
    by_uid = {f"{a['activity_id']}@cartlyf": a for a in expected}
    for event in events:
        assignment = by_uid[event["UID"]]
        assert event["DTSTART"] == _utc(assignment["start_at"])
        assert event["DTEND"] == _utc(assignment["end_at"])
        assert event["SUMMARY"] == assignment["activity_name"]
        assert event["DTSTAMP"] == _utc(version["published_at"])
    assert _ics(client, _token(feed)).text == response.text

    actions = fetch(
        superuser_url(migrated_pg),
        f"SELECT action FROM audit_log WHERE target_id = '{feed['id']}'",
    )
    assert actions == [("calendar_feed.created",)]


def test_TEN_05_revoked_feed_is_not_found(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    feed = _create(client, admin, built.lecturer_ids[0])
    token = _token(feed)
    assert _ics(client, token).status_code == 200

    revoke = client.delete(f"/api/v1/calendar-feeds/{feed['id']}", headers=admin.auth)
    assert revoke.status_code == 204, revoke.text
    revoked = _ics(client, token)
    assert revoked.status_code == 404
    assert revoked.headers["content-type"] == "application/problem+json"
    unknown = _ics(client, secrets.token_urlsafe(32))
    assert revoked.json() == unknown.json()

    # Revoking again is a no-op, not an error, and is audited once.
    again = client.delete(f"/api/v1/calendar-feeds/{feed['id']}", headers=admin.auth)
    assert again.status_code == 204
    listed = client.get(
        f"/api/v1/resources/{built.lecturer_ids[0]}/calendar-feeds", headers=admin.auth
    ).json()
    assert [f["id"] for f in listed] == [feed["id"]]
    assert listed[0]["revoked_at"] is not None
    actions = fetch(
        superuser_url(migrated_pg),
        f"SELECT action FROM audit_log WHERE target_id = '{feed['id']}' ORDER BY created_at",
    )
    assert actions == [("calendar_feed.created",), ("calendar_feed.revoked",)]


def test_TEN_05_unknown_token_is_not_found(client: TestClient, app: FastAPI) -> None:
    for token in [secrets.token_urlsafe(32), "x", "a" * 200]:
        response = _ics(client, token)
        assert response.status_code == 404, token
        assert response.json()["title"] == "Not Found"


def test_TEN_05_feed_of_deleted_resource_is_not_found(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    resource = client.post(
        "/api/v1/resources",
        headers=admin.auth,
        json={"resource_type_id": built.lecturer_type_id, "code": "GONE", "name": "Gone"},
    ).json()["id"]
    token = _token(_create(client, admin, resource))
    assert _ics(client, token).status_code == 200
    deleted = client.delete(f"/api/v1/resources/{resource}", headers=admin.auth)
    assert deleted.status_code == 204, deleted.text
    assert _ics(client, token).status_code == 404


def test_TEN_05_other_org_cannot_manage_feed(client: TestClient, app: FastAPI) -> None:
    a_admin = signup_and_confirm(client, app, org_name="Org A")
    b_admin = signup_and_confirm(client, app, org_name="Org B")
    resource = build_schedule(client, a_admin).lecturer_ids[0]
    feed = _create(client, a_admin, resource)
    base = f"/api/v1/resources/{resource}/calendar-feeds"

    assert client.get(base, headers=b_admin.auth).status_code == 404
    assert client.post(base, headers=b_admin.auth).status_code == 404
    revoke = client.delete(f"/api/v1/calendar-feeds/{feed['id']}", headers=b_admin.auth)
    assert revoke.status_code == 404
    assert client.get("/api/v1/me/calendar-feeds", headers=b_admin.auth).status_code == 404
    assert _ics(client, _token(feed)).status_code == 200


def test_JOB_07_publish_refreshes_feed(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2, sessions=1)
    token = _token(_create(client, admin, built.lecturer_ids[0]))
    assert _events(_ics(client, token).text) == []

    _, v1 = solve_now(client, admin, built.schedule_id)
    assert _events(_ics(client, token).text) == [], "a draft must not reach the feed"
    assert publish(client, admin, v1).status_code == 200
    first = get_version(client, admin, v1)["assignments"]
    events = _events(_ics(client, token).text)
    assert {e["UID"] for e in events} == {f"{a['activity_id']}@cartlyf" for a in first}

    target = first[0]
    to = free_start(first)
    moved = move(client, admin, v1, target, to)
    assert moved.status_code == 201, moved.text
    assert publish(client, admin, moved.json()["id"]).status_code == 200
    events = {e["UID"]: e for e in _events(_ics(client, token).text)}
    assert len(events) == len(first)
    assert events[f"{target['activity_id']}@cartlyf"]["DTSTART"] == _utc(to)


def test_member_can_create_own_feed(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    resource = build_schedule(client, admin).lecturer_ids[0]
    assert client.post("/api/v1/me/calendar-feeds", headers=member.auth).status_code == 404

    _link(client, admin, resource, member)
    created = client.post("/api/v1/me/calendar-feeds", headers=member.auth)
    assert created.status_code == 201, created.text
    feed = created.json()
    assert feed["resource_id"] == resource
    assert _ics(client, _token(feed)).status_code == 200
    listed = client.get("/api/v1/me/calendar-feeds", headers=member.auth)
    assert listed.status_code == 200
    assert [f["id"] for f in listed.json()] == [feed["id"]]

    revoke = client.delete(f"/api/v1/calendar-feeds/{feed['id']}", headers=member.auth)
    assert revoke.status_code == 204
    assert _ics(client, _token(feed)).status_code == 404


def test_member_cannot_create_feed_for_other_resource(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin, lecturers=2)
    own, other = built.lecturer_ids
    _link(client, admin, own, member)
    others_feed = _create(client, admin, other)

    # Resource routes are configuration, which members may not touch (AUTH-06).
    for resource in (own, other):
        base = f"/api/v1/resources/{resource}/calendar-feeds"
        assert client.post(base, headers=member.auth).status_code == 403
        assert client.get(base, headers=member.auth).status_code == 403
    revoke = client.delete(f"/api/v1/calendar-feeds/{others_feed['id']}", headers=member.auth)
    assert revoke.status_code == 404
    assert _ics(client, _token(others_feed)).status_code == 200


def test_viewer_cannot_manage_feeds(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    viewer = add_member(client, app, admin, ["viewer"])
    resource = build_schedule(client, admin).lecturer_ids[0]
    feed = _create(client, admin, resource)
    base = f"/api/v1/resources/{resource}/calendar-feeds"
    assert client.get(base, headers=viewer.auth).status_code == 403
    assert client.post(base, headers=viewer.auth).status_code == 403
    assert client.get("/api/v1/me/calendar-feeds", headers=viewer.auth).status_code == 403
    assert client.post("/api/v1/me/calendar-feeds", headers=viewer.auth).status_code == 403
    revoke = client.delete(f"/api/v1/calendar-feeds/{feed['id']}", headers=viewer.auth)
    assert revoke.status_code == 403


def test_feed_token_never_listed(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    resource = build_schedule(client, admin).lecturer_ids[0]
    feed = _create(client, admin, resource)
    token = _token(feed)
    listed = client.get(f"/api/v1/resources/{resource}/calendar-feeds", headers=admin.auth)
    assert listed.status_code == 200
    assert token not in listed.text
    assert [set(f) for f in listed.json()] == [{"id", "resource_id", "created_at", "revoked_at"}]
    stored = fetch(
        superuser_url(migrated_pg),
        f"SELECT token_hash FROM calendar_feed WHERE id = '{feed['id']}'",
    )
    assert stored == [(hashlib.sha256(token.encode()).digest(),)]


def test_feed_requests_are_rate_limited(client: TestClient, app: FastAPI) -> None:
    app.state.settings = app.state.settings.model_copy(update={"feed_rate_limit_per_minute": 2})
    token = secrets.token_urlsafe(32)
    assert [_ics(client, token).status_code for _ in range(3)] == [404, 404, 429]
