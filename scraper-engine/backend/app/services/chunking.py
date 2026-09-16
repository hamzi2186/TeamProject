import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    content_hash: str
    token_count: int


class DeterministicChunker:
    def __init__(self, *, max_tokens: int = 850, overlap_tokens: int = 120) -> None:
        if max_tokens < 1 or overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("Chunk token settings are invalid")
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens

    def chunk(self, text: str) -> list[TextChunk]:
        matches = list(re.finditer(r"\w+|[^\w\s]", text, re.UNICODE))
        if not matches:
            return []
        boundaries = [
            index + 1
            for index, match in enumerate(matches[:-1])
            if "\n\n" in text[match.end() : matches[index + 1].start()]
        ]
        boundaries.append(len(matches))
        chunks: list[TextChunk] = []
        start = 0
        while start < len(matches):
            hard_end = min(start + self._max_tokens, len(matches))
            candidates = [boundary for boundary in boundaries if start < boundary <= hard_end]
            end = max(candidates) if candidates else hard_end
            content = text[matches[start].start() : matches[end - 1].end()].strip()
            if content:
                chunks.append(
                    TextChunk(
                        index=len(chunks),
                        content=content,
                        content_hash=hashlib.sha256(content.encode()).hexdigest(),
                        token_count=end - start,
                    )
                )
            if end >= len(matches):
                break
            start = max(start + 1, end - self._overlap_tokens)
        return chunks
