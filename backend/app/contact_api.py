from html import escape

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .config import settings

router = APIRouter(prefix="/api/v1")

CONTACT_ADDRESS = "psidp@giving.plus.bi"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
RESEND_EMAILS_URL = "https://api.resend.com/emails"


class ContactMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    message: str = Field(min_length=1, max_length=5000)
    turnstile_token: str = Field(min_length=1, max_length=2048)
    website: str = Field(default="", max_length=200)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


@router.get("/contact/config")
def contact_config():
    site_key = settings().turnstile_site_key
    if not site_key:
        raise HTTPException(status_code=503, detail="Contact form is not configured")
    return {"site_key": site_key}


@router.post("/contact")
async def send_contact_message(payload: ContactMessage):
    config = settings()
    if not config.turnstile_secret_key or not config.resend_api_key:
        raise HTTPException(status_code=503, detail="Contact form is not configured")

    # Quietly accept the hidden honeypot so simple form bots do not receive feedback.
    if payload.website:
        return {"sent": True}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            verification = await client.post(
                TURNSTILE_VERIFY_URL,
                data={"secret": config.turnstile_secret_key, "response": payload.turnstile_token},
            )
            verification.raise_for_status()
            verification_result = verification.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(status_code=503, detail="Spam protection is temporarily unavailable") from None
        if not isinstance(verification_result, dict) or verification_result.get("success") is not True:
            raise HTTPException(status_code=400, detail="Please complete the spam check and try again")

        email = str(payload.email)
        message = payload.message
        try:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={"Authorization": f"Bearer {config.resend_api_key}"},
                json={
                    "from": f"Project Studies Portal <{CONTACT_ADDRESS}>",
                    "to": [CONTACT_ADDRESS],
                    "reply_to": email,
                    "subject": "New message from Project Studies Portal",
                    "text": f"From: {email}\n\n{message}",
                    "html": (
                        f"<p><strong>From:</strong> {escape(email)}</p>"
                        f"<p>{escape(message).replace(chr(10), '<br>')}</p>"
                    ),
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Could not send your message. Please try again later") from None

    return {"sent": True}
