import hashlib
import re
from dataclasses import dataclass, field

import trafilatura
from bs4 import BeautifulSoup

from app.services.urls import canonicalize_crawl_url

WHITESPACE = re.compile(r"[ \t\r\f\v]+")
EXCESS_NEWLINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class ExtractedPage:
    title: str | None
    meta_description: str | None
    canonical_url: str
    text: str
    content_hash: str
    links: list[str] = field(default_factory=list)


def normalize_text(value: str) -> str:
    lines = [WHITESPACE.sub(" ", line).strip() for line in value.splitlines()]
    return EXCESS_NEWLINES.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def extract_page(html: str, *, url: str) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "template", "svg"]):
        element.decompose()
    title = normalize_text(soup.title.get_text(" ")) if soup.title else None
    description = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = normalize_text(str(description.get("content", ""))) if description else None
    canonical = soup.find("link", attrs={"rel": lambda value: value and "canonical" in value})
    canonical_url = (
        canonicalize_crawl_url(
            str(canonical.get("href")) if canonical and canonical.get("href") else url,
            base_url=url,
        )
        or url
    )
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        include_links=False,
        favor_precision=True,
        output_format="txt",
    )
    if not extracted:
        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            include_links=False,
            output_format="txt",
        )
    if not extracted:
        for candidate in (soup.find("main"), soup.find("article"), soup.body):
            if candidate:
                candidate_text = candidate.get_text("\n", strip=True)
                if len(candidate_text) >= 50:
                    extracted = candidate_text
                    break
        else:
            extracted = soup.body.get_text("\n", strip=True) if soup.body else ""
    text = normalize_text(extracted)
    links = []
    for anchor in soup.find_all("a", href=True):
        link = canonicalize_crawl_url(str(anchor["href"]), base_url=url)
        if link:
            links.append(link)
    return ExtractedPage(
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        links=list(dict.fromkeys(links)),
    )
