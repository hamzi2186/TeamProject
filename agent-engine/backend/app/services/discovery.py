import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DiscoveredDocument:
    module_key: str
    source_path: str
    file_name: str
    absolute_path: Path
    title: str
    raw_content: str
    content_hash: str


class DocumentDiscoveryService:
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).resolve()

    def discover(self, module_filter: str | None = None) -> list[DiscoveredDocument]:
        if not self.root_path.exists() or not self.root_path.is_dir():
            return []

        discovered: list[DiscoveredDocument] = []
        normalized_filter = module_filter.strip().casefold() if module_filter else None

        for path in self.root_path.rglob("*.md"):
            if not path.is_file():
                continue

            # Skip hidden files or files in hidden folders
            resolved_path = path.resolve()
            try:
                relative = resolved_path.relative_to(self.root_path)
            except ValueError:
                # Path traversal / outside root
                continue

            parts = relative.parts
            if any(part.startswith(".") for part in parts):
                continue

            # Determine module_key
            if len(parts) > 1:
                module_key = parts[0].casefold()
            else:
                module_key = "general"

            if normalized_filter and module_key != normalized_filter:
                continue

            source_path = relative.as_posix()
            try:
                content = resolved_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            title = self._extract_title(content, path.stem)

            discovered.append(
                DiscoveredDocument(
                    module_key=module_key,
                    source_path=source_path,
                    file_name=path.name,
                    absolute_path=resolved_path,
                    title=title,
                    raw_content=content,
                    content_hash=content_hash,
                )
            )

        discovered.sort(key=lambda d: d.source_path)
        return discovered

    @staticmethod
    def _extract_title(content: str, fallback_stem: str) -> str:
        # 1. Try YAML frontmatter
        if content.startswith("---"):
            end_idx = content.find("\n---", 3)
            if end_idx != -1:
                frontmatter_text = content[3:end_idx].strip()
                try:
                    data = yaml.safe_load(frontmatter_text)
                    if isinstance(data, dict) and data.get("title"):
                        return str(data["title"]).strip()
                except Exception:
                    pass

        # 2. Look for top-level Markdown header # Header
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("# ") and not line.startswith("##"):
                clean_title = line[2:].strip()
                # Strip basic markdown link syntax e.g. [text](url) -> text
                clean_title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_title)
                # Strip bold/italics/backticks
                clean_title = clean_title.strip("`*#_ ")
                if clean_title:
                    return clean_title

        # 3. Fallback to stem
        clean_stem = fallback_stem.replace("-", " ").replace("_", " ").title()
        return clean_stem

