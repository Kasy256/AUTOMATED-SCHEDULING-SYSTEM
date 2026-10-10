from cartlyf_api.email.provider import EmailMessage
from cartlyf_api.settings import Settings


def link(settings: Settings, path: str, token: str) -> str:
    return f"{str(settings.web_base_url).rstrip('/')}/{path}?token={token}"


def confirm_email(settings: Settings, to: str, token: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="Confirm your email address",
        body=(
            "Welcome to Cartlyf.\n\n"
            "Confirm your email address to finish creating your organisation:\n"
            f"{link(settings, 'confirm-email', token)}\n\n"
            "This link expires in 24 hours. If you did not sign up, ignore this email."
        ),
    )


def account_exists(settings: Settings, to: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="You already have a Cartlyf account",
        body=(
            "Someone tried to sign up with this email address, but you already have an account.\n\n"
            f"Log in at {str(settings.web_base_url).rstrip('/')}/login\n\n"
            "If this was not you, you can ignore this email."
        ),
    )


def invitation(settings: Settings, to: str, organisation_name: str, token: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject=f"You have been invited to {organisation_name} on Cartlyf",
        body=(
            f"You have been invited to join {organisation_name} on Cartlyf.\n\n"
            f"Accept the invitation:\n{link(settings, 'accept-invitation', token)}\n\n"
            "This link expires in 7 days."
        ),
    )
