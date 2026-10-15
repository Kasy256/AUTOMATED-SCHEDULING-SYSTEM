from uuid import uuid4

from cartlyf_api.email import messages
from support import make_settings


def test_links_point_at_web_app_without_double_slash() -> None:
    settings = make_settings(
        "postgresql+asyncpg://u:p@h/db", "redis://h:1/0", web_base_url="https://app.example.com/"
    )
    message = messages.confirm_email(settings, "a@example.com", "tok.en-1")
    assert message.to == "a@example.com"
    assert "https://app.example.com/confirm-email?token=tok.en-1" in message.body


def test_invitation_names_the_organisation() -> None:
    settings = make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0")
    message = messages.invitation(settings, "b@example.com", "Kampala Clinic", "t")
    assert "Kampala Clinic" in message.subject
    assert "http://web.test/accept-invitation?token=t" in message.body


def test_account_exists_has_no_link_token() -> None:
    settings = make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0")
    message = messages.account_exists(settings, "c@example.com")
    assert "already have an account" in message.body
    assert "token=" not in message.body


def test_schedule_published_links_the_version_and_counts_assignments() -> None:
    settings = make_settings(
        "postgresql+asyncpg://u:p@h/db", "redis://h:1/0", web_base_url="https://app.example.com/"
    )
    schedule_id, version_id = uuid4(), uuid4()
    message = messages.schedule_published(
        settings, "d@example.com", "Term 1", schedule_id, version_id, 1
    )
    assert "Term 1" in message.subject
    assert f"https://app.example.com/schedules/{schedule_id}/versions/{version_id}" in message.body
    assert "1 assignment " in message.body
    plural = messages.schedule_published(settings, "d@example.com", "T", schedule_id, version_id, 3)
    assert "3 assignments" in plural.body
