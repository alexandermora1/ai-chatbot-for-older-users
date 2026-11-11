"""Fetch public guidance pages and reduce them to clean text.

A page becomes a list of "units": headings and paragraphs in reading order.
Menus, footers, scripts and forms are removed, so only the guidance text is left.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Tag

USER_AGENT = "ai-chatbot-for-older-users/0.1 (personal learning project)"
NOISE_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button", "iframe"]
HEADING_TAGS = ["h1", "h2", "h3", "h4"]
TEXT_TAGS = ["p", "li"]


@dataclass
class Unit:
    kind: str  # "heading" or "text"
    text: str


@dataclass
class Page:
    id: str
    topic: str
    url: str
    title: str
    fetched: str
    units: list[Unit] = field(default_factory=list)

    @property
    def text_length(self) -> int:
        return sum(len(u.text) for u in self.units if u.kind == "text")


def load_sources(path: Path) -> list[dict]:
    """Return the enabled entries from sources.json."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [s for s in data["sources"] if s.get("enabled", True)]


def _clean(text: str) -> str:
    return " ".join(text.split())


def extract(html: str, *, id: str, topic: str, url: str) -> Page:
    """Turn raw HTML into a Page with headings and paragraphs."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = _clean(title_tag.get_text()) if title_tag else url

    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    root = soup.find("main") or soup.find(id="main-content") or soup.find("article") or soup.body or soup

    units: list[Unit] = []
    seen: set[str] = set()
    for el in root.find_all(HEADING_TAGS + TEXT_TAGS):
        if not isinstance(el, Tag):
            continue
        # Text inside a list item is already part of that list item.
        if el.find_parent("li") is not None:
            continue
        text = _clean(el.get_text(" "))
        if not text:
            continue
        if el.name in HEADING_TAGS:
            if el.name == "h1":
                title = text
            units.append(Unit("heading", text))
            continue
        if el.name == "li":
            parent = el.parent
            if parent is not None and parent.name == "ol":
                number = len(el.find_previous_siblings("li")) + 1
                text = f"{number}. {text}"
            else:
                text = f"- {text}"
        # Many sites repeat teaser texts. Keep the first occurrence only.
        if text in seen:
            continue
        seen.add(text)
        units.append(Unit("text", text))

    return Page(id=id, topic=topic, url=url, title=title, fetched=date.today().isoformat(), units=units)


class RobotsCache:
    """Checks robots.txt once per site."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._parsers:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                response = self._client.get(f"{base}/robots.txt")
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser = None  # No robots.txt: nothing is disallowed.
            except httpx.HTTPError:
                parser = None
            self._parsers[base] = parser
        parser = self._parsers[base]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)


def fetch_all(sources: list[dict], raw_dir: Path, *, delay_seconds: float = 1.0) -> list[tuple[dict, str]]:
    """Fetch every source, save it as JSON in raw_dir, and return a list of problems."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    problems: list[tuple[dict, str]] = []
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "nb,no;q=0.9"}
    with httpx.Client(headers=headers, timeout=20, follow_redirects=True) as client:
        robots = RobotsCache(client)
        for source in sources:
            url = source["url"]
            if not robots.allowed(url):
                problems.append((source, "disallowed by robots.txt"))
                continue
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as error:
                problems.append((source, f"could not fetch: {error}"))
                continue
            page = extract(response.text, id=source["id"], topic=source["topic"], url=url)
            if page.text_length < 200:
                problems.append((source, f"too little text ({page.text_length} characters), page may need JavaScript"))
                continue
            save_page(page, raw_dir)
            print(f"  ok  {source['id']}: {page.text_length} characters")
            time.sleep(delay_seconds)
    return problems


def save_page(page: Page, raw_dir: Path) -> None:
    (raw_dir / f"{page.id}.json").write_text(json.dumps(asdict(page), ensure_ascii=False, indent=2), encoding="utf-8")


def load_pages(raw_dir: Path) -> list[Page]:
    pages = []
    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        units = [Unit(**u) for u in data.pop("units")]
        pages.append(Page(**data, units=units))
    return pages
