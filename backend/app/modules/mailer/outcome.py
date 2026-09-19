from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta

from app.modules.mailer.contracts import EmailOutcome

# Where a reply stops being the lead's own words and starts quoting the thread. The lead's
# reply quotes our email, so anything after these markers is ours, not theirs.
_QUOTE_STARTS = (
    re.compile(r"\n[ \t]*on\s[^\n]{0,200}(?:\n[^\n]{0,120})?wrote:", re.I),
    re.compile(r"\n[ \t]*-{2,}\s*(?:original|forwarded)\s+message\s*-{2,}", re.I),
    re.compile(r"\n[ \t]*_{10,}[ \t]*\n"),
    re.compile(r"\n[ \t]*from:[^\n]+\n[ \t]*(?:sent|date):", re.I),
)

_UNSUBSCRIBE_PATTERNS = (
    r"\bunsubscribe\b",
    r"\bopt(?:ing)?[\s-]*out\b",
    r"\bremove\s+(?:me|us|my\s+(?:e-?mail|address|name))\b",
    r"\btake\s+(?:me|us)\s+off\b",
    r"\b(?:stop|quit|cease)\s+(?:e-?mailing|sending|contacting|messaging|writing|mailing)\b",
    r"\bplease\s+stop\b(?!\s+by\b)",
    r"\bdo\s*-?\s*not\s+(?:contact|e-?mail|message)\b",
    r"\bdon[’']?t\s+(?:contact|e-?mail|message)\s+(?:me|us)\b",
    r"\bno\s+(?:further|more)\s+(?:e-?mails?|messages?|contact)\b",
)
_UNSUBSCRIBE = re.compile("|".join(_UNSUBSCRIBE_PATTERNS), re.I)
_BARE_STOP = re.compile(r"^\W*stop\W*$", re.I)


def html_to_text(value: str | None) -> str:
    """Reduce an HTML email body to the lead's own text, dropping quoted history."""
    if not value:
        return ""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", value)
    text = re.sub(r"(?is)<blockquote\b.*?</blockquote>", " ", text)
    text = re.sub(r'(?is)<div[^>]*class="[^"]*gmail_quote.*', " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


def strip_quoted_reply(text: str | None) -> str:
    """Return only what the lead wrote, without the earlier messages they replied to."""
    if not text:
        return ""
    body = "\n" + text.replace("\r\n", "\n").replace("\r", "\n")
    cut = min((m.start() for pattern in _QUOTE_STARTS if (m := pattern.search(body))), default=len(body))
    lines = [line for line in body[:cut].split("\n") if not line.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def classify_stop_condition(text: str | None) -> bool:
    """True when the lead explicitly asks to stop hearing from us.

    Only their own words count. Replies quote our email, so matching the whole body would stop
    the thread whenever we had written the word ourselves. "Not interested" is not a stop here:
    it is an outcome the model classifies, and it still deserves a polite reply.
    """
    body = strip_quoted_reply(text)
    if not body:
        return False
    return bool(_BARE_STOP.match(body) or _UNSUBSCRIBE.search(body))


def should_continue_from_outcome(outcome: str | None) -> bool:
    if outcome is None:
        return True
    definitive = {
        EmailOutcome.NOT_INTERESTED,
        EmailOutcome.CONVERTED,
        EmailOutcome.DO_NOT_CONTACT,
        EmailOutcome.FAILED,
    }
    return outcome not in definitive


def compute_follow_up_at(outcome: str | None) -> datetime | None:
    if outcome == EmailOutcome.FOLLOW_UP_REQUIRED:
        return datetime.now(UTC) + timedelta(days=3)
    return None
