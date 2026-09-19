from __future__ import annotations

import hashlib
import hmac
import re
from email.header import decode_header
from typing import Iterable
from uuid import UUID

_SIGNATURE_LENGTH = 16


def extract_reply_to_token(address: str | None) -> str | None:
    if not address:
        return None
    match = re.search(r"\+([A-Za-z0-9._-]+)@", address)
    if match:
        return match.group(1)
    return None


def _sign(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return digest[:_SIGNATURE_LENGTH]


def make_reply_to_token(conversation_id: UUID, secret: str) -> str:
    """Derive the Reply-To token for a conversation, so nothing has to be stored.

    The token is the conversation id plus an HMAC of it. Anyone can read the id out of a
    Reply-To address, but only the holder of `secret` can produce a token that verifies.
    """
    if not secret:
        raise ValueError("a signing secret is required to build a Reply-To token")
    return f"{conversation_id.hex}-{_sign(conversation_id.hex, secret)}"


def resolve_reply_to_token(token: str | None, secret: str) -> UUID | None:
    """Return the conversation id a token was issued for, or None if it is not genuine."""
    if not token or not secret:
        return None
    key, separator, signature = token.strip().lower().partition("-")
    if not separator or len(key) != 32:
        return None
    if not hmac.compare_digest(signature, _sign(key, secret)):
        return None
    try:
        return UUID(hex=key)
    except ValueError:
        return None


def build_reply_to_address(*, mailbox: str, domain: str, token: str) -> str:
    return f"{mailbox}+{token}@{domain}"


def parse_address_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item]
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def decode_address_header(value: str | None) -> str | None:
    if not value:
        return None
    decoded_parts: list[str] = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


_MESSAGE_ID = re.compile(r"<[^<>\s]+>")


def normalize_message_id(value: str | None) -> str:
    """Strip whitespace and angle brackets so `<a@x>` and `a@x` compare equal."""
    return (value or "").strip().strip("<>").strip()


def parse_message_ids(value: str | None) -> list[str]:
    """Split an In-Reply-To / References header into normalized Message-IDs, oldest first."""
    if not value:
        return []
    tokens = _MESSAGE_ID.findall(value) or value.split()
    return [message_id for message_id in (normalize_message_id(token) for token in tokens) if message_id]


async def correlate_email(email: dict, existing: Iterable[dict]) -> str | None:
    """return the matched conversation_id or None.

    Priority:
    1. Reply-To address/token tied to conversation
    2. In-Reply-To
    3. References
    4. provider message/thread identifiers
    5. sender + active campaign fallback only when unambiguous

    `existing` must already be scoped to the tenant by the caller.
    """
    items = list(existing)
    email_to = parse_address_list(email.get("to_addresses"))
    reply_token = None
    for address in email_to:
        token = extract_reply_to_token(address)
        if token:
            reply_token = token
            break
    if reply_token:
        for item in items:
            if str(item.get("reply_to_token") or "") == reply_token:
                return str(item["conversation_id"])

    # In-Reply-To and References carry RFC 5322 Message-IDs, so they can only match the
    # internet_message_id we stored. provider_email_id is a provider UUID, never a Message-ID.
    known_message_ids: dict[str, str] = {}
    for item in items:
        message_id = normalize_message_id(item.get("internet_message_id"))
        if message_id:
            known_message_ids[message_id] = str(item["conversation_id"])

    for message_id in parse_message_ids(email.get("in_reply_to")):
        if message_id in known_message_ids:
            return known_message_ids[message_id]

    # References grows down a thread (oldest first), so walk it newest first to find the
    # nearest ancestor we sent.
    for message_id in reversed(parse_message_ids(email.get("references_header"))):
        if message_id in known_message_ids:
            return known_message_ids[message_id]

    provider_email_id = (email.get("provider_email_id") or "").strip()
    if provider_email_id:
        for item in items:
            if str(item.get("provider_email_id") or "") == provider_email_id:
                return str(item["conversation_id"])

    sender = (email.get("from_address") or "").lower()
    campaign_id = email.get("campaign_id")
    lead_id = email.get("lead_id")
    if not sender or lead_id is None:
        # Without a sender and a resolved lead, `None == None` would match any conversation.
        return None
    candidates = []
    for item in items:
        if item.get("lead_id") == lead_id and item.get("campaign_id") == campaign_id:
            if str(item.get("from_address") or "").lower() == sender:
                candidates.append(item)
    if len(candidates) == 1:
        return str(candidates[0]["conversation_id"])
    return None
