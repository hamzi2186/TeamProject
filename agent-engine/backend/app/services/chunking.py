import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:
    chunk_index: int
    header_path: str | None
    content: str
    content_hash: str
    metadata: dict = field(default_factory=dict)


class MarkdownChunker:
    """Deterministic structural Markdown chunker that tracks header hierarchy

    and creates semantic units.
    """

    def __init__(self, max_chunk_chars: int = 1500, min_chunk_chars: int = 50) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars

    def chunk(self, text: str) -> list[DocumentChunk]:
        clean_text = text.strip()
        if not clean_text:
            return []

        # Strip YAML frontmatter if present
        if clean_text.startswith("---"):
            end_fm = clean_text.find("\n---", 3)
            if end_fm != -1:
                clean_text = clean_text[end_fm + 4 :].strip()

        sections = self._split_by_headings(clean_text)
        raw_chunks: list[tuple[str | None, str]] = []

        for header_path, section_content in sections:
            section_content = section_content.strip()
            if not section_content:
                continue

            if len(section_content) <= self.max_chunk_chars:
                raw_chunks.append((header_path, section_content))
            else:
                # Split large section by paragraphs
                sub_chunks = self._split_large_section(section_content, self.max_chunk_chars)
                for sc in sub_chunks:
                    raw_chunks.append((header_path, sc))

        # Build DocumentChunk objects
        chunks: list[DocumentChunk] = []
        for idx, (h_path, content) in enumerate(raw_chunks):
            content = content.strip()
            if not content:
                continue
            c_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            chunks.append(
                DocumentChunk(
                    chunk_index=idx,
                    header_path=h_path,
                    content=content,
                    content_hash=c_hash,
                    metadata={
                        "char_count": len(content),
                        "word_count": len(content.split()),
                    },
                )
            )

        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str | None, str]]:
        """Splits markdown text into sections while tracking header hierarchy."""
        lines = text.splitlines()
        header_stack: list[tuple[int, str]] = []  # (level, title)

        sections: list[tuple[str | None, list[str]]] = []
        current_lines: list[str] = []
        current_header_path: str | None = None

        header_re = re.compile(r"^(#{1,6})\s+(.+)$")
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block

            m = header_re.match(line) if not in_code_block else None
            if m:
                # Save previous section if it had content
                if current_lines:
                    text_content = "\n".join(current_lines).strip()
                    if text_content:
                        sections.append((current_header_path, current_lines))
                    current_lines = []

                level = len(m.group(1))
                title = m.group(2).strip()
                # Clean title
                title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title).strip("`*#_ ")

                # Update header stack
                while header_stack and header_stack[-1][0] >= level:
                    header_stack.pop()
                header_stack.append((level, title))

                current_header_path = " > ".join(t for _, t in header_stack)
                # Keep heading line as part of section context
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            text_content = "\n".join(current_lines).strip()
            if text_content:
                sections.append((current_header_path, current_lines))

        return [(h, "\n".join(l_list).strip()) for h, l_list in sections]

    def _split_large_section(self, text: str, max_chars: int) -> list[str]:
        """Splits a large text section into smaller chunks along paragraph boundaries."""
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for p in paragraphs:
            p_str = p.strip()
            if not p_str:
                continue

            p_len = len(p_str)
            if current_len + p_len + 2 > max_chars and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [p_str]
                current_len = p_len
            else:
                current_chunk.append(p_str)
                current_len += p_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

