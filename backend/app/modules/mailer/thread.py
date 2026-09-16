from __future__ import annotations

import re
from email.header import decode_header
from typing import Iterable


def extract_reply_to_token(address: str | None) -> str | None:
    if not address:
        return None
    match = re.search(r"\+([A-Za-z0-9._-]+)@", address)
    if match:
        return match.group(1)
    return None


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


async def correlate_email(email: dict, existing: Iterable[dict]) -> str | None:
    """return the matched conversation_id or None.

    Priority:
    1. Reply-To address/token tied to conversation
    2. In-Reply-To
    3. References
    4. provider message/thread identifiers
    5. sender + active campaign fallback only when unambiguous
    """
    email_to = parse_address_list(email.get("to_addresses"))
    reply_token = None
    for address in email_to:
        token = extract_reply_to_token(address)
        if token:
            reply_token = token
            break
    if reply_token:
        for item in existing:
            if str(item.get("reply_to_token") or "") == reply_token:
                return str(item["conversation_id"])

    inbound_message_id = (email.get("in_reply_to") or "").strip()
    if inbound_message_id:
        for item in existing:
            if str(item.get("provider_email_id") or "") == inbound_message_id or str(
                item.get("internet_message_id") or ""
            ) == inbound_message_id:
                return str(item["conversation_id"])

    references = (email.get("references_header") or "").strip()
    if references:
        for item in existing:
            if str(item.get("references_header") or "") and references in str(
                item.get("references_header")
            ):
                return str(item["conversation_id"])

    provider_email_id = (email.get("provider_email_id") or "").strip()
    if provider_email_id:
        for item in existing:
            if str(item.get("provider_email_id") or "") == provider_email_id:
                return str(item["conversation_id"])

    sender = (email.get("from_address") or "").lower()
    campaign_id = email.get("campaign_id")
    candidates = []
    for item in existing:
        if item.get("lead_id") == email.get("lead_id") and item.get("campaign_id") == campaign_id:
            if str(item.get("from_address") or "").lower() == sender:
                candidates.append(item)
    if len(candidates) == 1:
        return str(candidates[0]["conversation_id"])
    return None
