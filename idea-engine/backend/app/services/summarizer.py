import httpx
from app.core.config import get_settings
from app.core.logging import logger
from app.schemas.enums import Channel, Direction
from app.schemas.reports import TimelineEvent


def synthesize_approach_summary(events: list[TimelineEvent]) -> str:
    """
    Constructs a factual narrative detailing how the lead was approached,
    including the sequence of channels, timestamps, and touchpoint counts.
    """
    if not events:
        return "No outreach touchpoints initiated yet."

    channel_counts: dict[str, int] = {}
    for event in events:
        channel_counts[event.channel.value] = channel_counts.get(event.channel.value, 0) + 1

    channel_breakdown = ", ".join(
        f"{count} {chan}" for chan, count in channel_counts.items()
    )

    first_event = events[0]
    last_event = events[-1]

    touchpoint_descriptions = []
    for i, e in enumerate(events[:5], start=1):
        direction_str = "Outbound" if e.direction == Direction.OUTBOUND else "Inbound"
        time_str = e.timestamp.strftime("%Y-%m-%d %H:%M")
        detail = ""
        if e.channel == Channel.CALL:
            duration = f"{e.duration_seconds}s" if e.duration_seconds is not None else "n/a"
            detail = f" (duration: {duration})"
        elif e.channel == Channel.EMAIL and e.subject:
            detail = f" (subject: '{e.subject[:30]}')"
        touchpoint_descriptions.append(f"Step {i}: {direction_str} {e.channel.value} at {time_str}{detail}")

    if len(events) > 5:
        touchpoint_descriptions.append(f"... and {len(events) - 5} subsequent touchpoint(s).")

    summary = (
        f"Approached across {len(events)} total touchpoint(s) ({channel_breakdown}). "
        f"First contact initiated via {first_event.channel.value} on {first_event.timestamp.strftime('%Y-%m-%d at %H:%M UTC')}. "
        f"Latest interaction on {last_event.timestamp.strftime('%Y-%m-%d at %H:%M UTC')}.\n"
        + " \u2192 ".join(touchpoint_descriptions)
    )
    return summary


async def synthesize_conversation_summary(
    events: list[TimelineEvent],
    lead_name: str,
) -> str:
    """
    Synthesizes what happened in the multi-channel conversations.
    Uses deterministic synthesis as default and falls back gracefully
    if TPI LLM service is unavailable or disabled.
    """
    if not events:
        return f"No conversation history recorded for {lead_name}."

    # Try enhanced TPI LLM synthesis if available
    settings = get_settings()
    if settings.tpi_api_base_url and settings.app_env != "test":
        try:
            llm_summary = await _call_tpi_llm_summary(events, lead_name, settings.tpi_api_base_url)
            if llm_summary:
                return llm_summary
        except Exception as exc:
            logger.debug(f"TPI LLM summary unavailable, using deterministic synthesis: {exc}")

    return _deterministic_conversation_summary(events, lead_name)


def _deterministic_conversation_summary(
    events: list[TimelineEvent],
    lead_name: str,
) -> str:
    """
    Factual deterministic summary based strictly on persisted event records.
    """
    inbound_msgs = [e for e in events if e.direction == Direction.INBOUND]
    outbound_msgs = [e for e in events if e.direction == Direction.OUTBOUND]
    calls = [e for e in events if e.channel == Channel.CALL]

    lines = []
    lines.append(
        f"Outreach to {lead_name} included {len(outbound_msgs)} outbound touchpoint(s) "
        f"and received {len(inbound_msgs)} inbound response(s)."
    )

    if calls:
        call_summaries = []
        for c in calls:
            dur = f"{c.duration_seconds}s" if c.duration_seconds is not None else "0s"
            status = c.outcome or c.delivery_status or "completed"
            call_summaries.append(f"Call on {c.timestamp.strftime('%m/%d %H:%M')} (duration: {dur}, status: {status})")
        lines.append("Voice calls: " + "; ".join(call_summaries) + ".")

    if inbound_msgs:
        inbound_snippets = []
        for msg in inbound_msgs[:3]:
            snippet = msg.content.strip().replace("\n", " ")
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            inbound_snippets.append(f"[{msg.channel.value}]: \"{snippet}\"")
        lines.append("Key inbound feedback: " + " | ".join(inbound_snippets))
    else:
        lines.append("No inbound reply received to date across any channel.")

    return "\n".join(lines)


async def _call_tpi_llm_summary(
    events: list[TimelineEvent],
    lead_name: str,
    tpi_base_url: str,
) -> str | None:
    """
    Calls TPI LLM service endpoint without storing or using vendor credentials.
    """
    transcript_lines = []
    for e in events:
        actor = "Lead" if e.direction == Direction.INBOUND else "T Rex Agent"
        transcript_lines.append(f"[{e.timestamp.strftime('%H:%M')} - {e.channel.value}] {actor}: {e.content[:120]}")

    payload = {
        "prompt": (
            f"Provide a concise, 2-3 sentence executive summary of the following outreach conversations with lead '{lead_name}'. "
            "Highlight key interest or objections stated."
        ),
        "context": "\n".join(transcript_lines),
    }

    settings = get_settings()
    headers = {}
    if settings.tpi_internal_service_token:
        headers["x-tpi-service-token"] = settings.tpi_internal_service_token

    async with httpx.AsyncClient(timeout=4.0) as client:
        resp = await client.post(
            f"{tpi_base_url}/api/v1/tpi/llm/generate",
            json=payload,
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "text" in data:
                return data["text"]
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                return data["data"].get("text")
    return None
