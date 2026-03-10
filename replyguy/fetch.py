from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable
from xml.etree import ElementTree

USER_AGENT = "replyguy/0.0.0"


@dataclass
class FetchedSource:
    url: str
    title: str
    text: str
    content_type: str


def _get(url: str, timeout: int = 20) -> requests.Response:
    import requests

    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def _parse_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    pages: list[str] = []
    for page in reader.pages[:8]:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages).strip()


def _parse_html(url: str, text: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    body = soup.get_text("\n", strip=True)
    trimmed = "\n".join(line for line in body.splitlines() if line.strip())[:12000]
    return title, trimmed


def _parse_feed(url: str, text: str) -> tuple[str, str]:
    root = ElementTree.fromstring(text)
    items: list[str] = []
    title = url
    channel = root.find("channel")
    if channel is not None:
        title_node = channel.find("title")
        if title_node is not None and title_node.text:
            title = title_node.text.strip()
        entries = channel.findall("item")[:8]
        for item in entries:
            item_title = (item.findtext("title") or "").strip()
            item_link = (item.findtext("link") or "").strip()
            item_desc = (item.findtext("description") or "").strip()
            items.append(f"- {item_title}\n  {item_link}\n  {item_desc}".strip())
        return title, "\n\n".join(items).strip()
    ns_entries = root.findall("{http://www.w3.org/2005/Atom}entry")[:8]
    feed_title = root.findtext("{http://www.w3.org/2005/Atom}title")
    if feed_title:
        title = feed_title.strip()
    for entry in ns_entries:
        item_title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        item_link = link_node.attrib.get("href", "").strip() if link_node is not None else ""
        summary = (
            entry.findtext("{http://www.w3.org/2005/Atom}summary")
            or entry.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        ).strip()
        items.append(f"- {item_title}\n  {item_link}\n  {summary}".strip())
    return title, "\n\n".join(items).strip()


def fetch_url(url: str) -> FetchedSource:
    response = _get(url)
    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        text = _parse_pdf(response.content)
        return FetchedSource(url=url, title=url, text=text, content_type=content_type or "application/pdf")
    body_text = response.text
    stripped = body_text.lstrip()
    if "xml" in content_type or stripped.startswith("<?xml") or "<rss" in stripped[:200] or "<feed" in stripped[:200]:
        title, text = _parse_feed(url, body_text)
        return FetchedSource(url=url, title=title, text=text, content_type=content_type or "application/xml")
    title, text = _parse_html(url, body_text)
    return FetchedSource(url=url, title=title, text=text, content_type=content_type or "text/html")


def fetch_many(urls: Iterable[str], limit: int = 5) -> list[FetchedSource]:
    items: list[FetchedSource] = []
    for url in list(urls)[:limit]:
        try:
            items.append(fetch_url(url))
        except Exception:
            continue
    return items
