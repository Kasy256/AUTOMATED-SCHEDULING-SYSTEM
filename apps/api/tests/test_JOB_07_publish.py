from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import (
    add_member,
    build_schedule,
    free_start,
    get_version,
    move,
    publish,
    sent_emails,
    signup_and_confirm,
    solve_now,
)

pytestmark = pytest.mark.integration


def test_JOB_07_publish_emails_affected_members(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin, demands=2, sessions=1)
    me = client.get("/api/v1/auth/me", headers=member.auth).json()["user_id"]
    linked = client.patch(
        f"/api/v1/resources/{built.lecturer_ids[0]}", headers=admin.auth, json={"user_id": me}
    )
    assert linked.status_code == 200, linked.text
    _, v1 = solve_now(client, admin, built.schedule_id)

    def published_mail(to: str) -> list[tuple[str, str]]:
        return [
            (m.subject, m.body)
            for m in sent_emails(app).sent
            if m.to == to and "/versions/" in m.body
        ]

    assert publish(client, admin, v1).status_code == 200
    mails = published_mail(member.email)
    assert len(mails) == 1
    subject, body = mails[0]
    assert "Solve term" in subject
    assert f"http://web.test/schedules/{built.schedule_id}/versions/{v1}" in body
    assert "2 assignments" in body
    assert published_mail(admin.email) == []

    # v2 re-places an activity where it already was: nobody's assignments change.
    first = get_version(client, admin, v1)["assignments"]
    same = move(client, admin, v1, first[0], datetime.fromisoformat(first[0]["start_at"]))
    assert same.status_code == 201, same.text
    assert publish(client, admin, same.json()["id"]).status_code == 200
    assert len(published_mail(member.email)) == 1

    moved = move(client, admin, same.json()["id"], first[0], free_start(first))
    assert moved.status_code == 201, moved.text
    v3 = moved.json()["id"]
    assert publish(client, admin, v3).status_code == 200
    mails = published_mail(member.email)
    assert len(mails) == 2
    assert f"/versions/{v3}" in mails[-1][1]
