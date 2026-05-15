from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from incident_collector.utils import extract_urls

from .models import utc_now_iso

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _fetch_with_retry(url: str) -> requests.Response:
    """Fetch a URL with up to 3 retries on transient network errors."""
    response = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
    return response


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MAX_READ_BYTES = 250_000


def classify_url(url: str) -> str:
    lower = url.lower()
    if "github.com" in lower:
        return "poc"
    if any(host in lower for host in ["etherscan.io", "bscscan.com", "arbiscan.io", "basescan.org", "external_explorer.com/explorer", "/tx/"]):
        return "explorer"
    if "x.com" in lower or "twitter.com" in lower:
        return "social"
    return "report"


def extract_addresses(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"0x[a-fA-F0-9]{40}", text)))


def extract_tx_hashes(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"0x[a-fA-F0-9]{64}", text)))


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self._in_title = False
        self.links: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "title":
            self._in_title = True
        href = attr_map.get("href")
        if tag == "a" and href:
            normalized = urljoin(self.base_url, href)
            if normalized.startswith("http://") or normalized.startswith("https://"):
                self.links.append(normalized)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title and not self.title:
            self.title = cleaned
        self.text_parts.append(cleaned)


@dataclass
class SourceDocument:
    source_id: str
    url: str
    source_type: str
    fetch_status: str
    fetched_at: str
    status_code: int | None = None
    content_type: str = ""
    title: str = ""
    text_excerpt: str = ""
    discovered_links: list[dict[str, str]] = field(default_factory=list)
    extracted_addresses: list[str] = field(default_factory=list)
    extracted_tx_hashes: list[str] = field(default_factory=list)
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _filter_links(base_url: str, links: list[str]) -> list[str]:
    base_host = urlparse(base_url).netloc.lower()
    base_path = urlparse(base_url).path
    ranked: list[str] = []
    seen: set[str] = set()
    for link in links:
        lower = link.lower()
        if any(skip in lower for skip in ["javascript:", "mailto:", "/cdn-cgi/"]):
            continue
        if "#" in link:
            link = link.split("#", 1)[0]
        if link in seen:
            continue
        seen.add(link)
        ranked.append(link)

    interesting: list[str] = []
    for link in ranked:
        parsed = urlparse(link)
        lower = link.lower()
        path = parsed.path or "/"
        if parsed.query and any(token in parsed.query.lower() for token in ["share", "utm_", "ref="]):
            continue
        if any(
            lower.endswith(suffix)
            for suffix in [
                "/blog",
                "/contact",
                "/about",
                "/settings",
                "/gastracker",
            ]
        ):
            continue
        if any(
            snippet in lower
            for snippet in [
                "/intent/tweet",
                "/share/url",
                "/tree/main",
                "/tree/main/src",
                "/tree/main/src/test",
                "/features/",
                "/login",
                "/signup",
            ]
        ):
            continue
        if "github.com" in base_host:
            if "/blob/" not in parsed.path and "/raw/" not in parsed.path:
                continue
            if "/features/" in parsed.path or "/login" in parsed.path or parsed.path in {"", "/"}:
                continue
        if "x.com" in base_host or "twitter.com" in base_host:
            path = parsed.path.strip("/")
            base_first_segment = base_path.strip("/").split("/", 1)[0]
            current_first_segment = path.split("/", 1)[0] if path else ""
            if base_first_segment and current_first_segment and current_first_segment.lower() != base_first_segment.lower():
                continue
            if path.count("/") > 2 and "/status/" not in parsed.path:
                continue
            if any(skip in parsed.path for skip in ["/tos", "/privacy", "/using-x/", "/articles/", "/imprint"]):
                continue
        if parsed.netloc.lower() == base_host and path in {"", "/", base_path}:
            continue
        if any(
            needle in lower
            for needle in [
                "github.com",
                "x.com",
                "twitter.com",
                "etherscan.io",
                "bscscan.com",
                "arbiscan.io",
                "basescan.org",
                "external_explorer.com",
                "medium.com",
                "certik.com",
                "slowmist",
                "verichains",
                "quillaudits",
                "bitfinding",
                "quadrigainitiative",
            ]
        ) or parsed.netloc.lower() == base_host:
            interesting.append(link)
    return interesting[:20]


def fetch_source_document(source_id: str, url: str, source_type: str) -> SourceDocument:
    fetched_at = utc_now_iso()
    try:
        response = _fetch_with_retry(url)
        status_code = response.status_code
        content_type = response.headers.get("Content-Type", "")
        raw = response.content[:MAX_READ_BYTES]
        if response.status_code >= 400:
            logger.warning(
                "source.fetch_http_error",
                extra={"source_id": source_id, "url": url, "status_code": response.status_code},
            )
            return SourceDocument(
                source_id=source_id,
                url=url,
                source_type=source_type,
                fetch_status="http_error",
                fetched_at=fetched_at,
                status_code=response.status_code,
                content_type=content_type,
                error_message=f"HTTP {response.status_code}",
            )
    except requests.RequestException as exc:
        logger.warning(
            "source.fetch_network_error",
            extra={"source_id": source_id, "url": url, "error": str(exc)},
        )
        return SourceDocument(
            source_id=source_id,
            url=url,
            source_type=source_type,
            fetch_status="network_error",
            fetched_at=fetched_at,
            error_message=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "source.fetch_failed",
            extra={"source_id": source_id, "url": url, "error": str(exc)},
        )
        return SourceDocument(
            source_id=source_id,
            url=url,
            source_type=source_type,
            fetch_status="failed",
            fetched_at=fetched_at,
            error_message=str(exc),
        )

    text = raw.decode("utf-8", errors="ignore")
    links: list[str] = []
    title = ""
    visible_text = text
    if "html" in content_type.lower() or "<html" in text.lower():
        parser = LinkParser(base_url=url)
        parser.feed(text)
        title = parser.title
        links = _filter_links(url, parser.links)
        visible_text = " ".join(parser.text_parts)

    excerpt = " ".join(visible_text.split())[:1200]
    tx_hashes = extract_tx_hashes(visible_text)
    addresses = extract_addresses(visible_text)
    discovered_links = [
        {
            "url": link,
            "source_type": classify_url(link),
            "discovered_from": source_id,
        }
        for link in links
    ]

    return SourceDocument(
        source_id=source_id,
        url=url,
        source_type=source_type,
        fetch_status="fetched",
        fetched_at=fetched_at,
        status_code=status_code,
        content_type=content_type,
        title=title,
        text_excerpt=excerpt,
        discovered_links=discovered_links,
        extracted_addresses=addresses[:20],
        extracted_tx_hashes=tx_hashes[:20],
    )


def normalize_url(url: str) -> str:
    """Return a canonical URL key for deduplication (lowercase host, no trailing slash, no fragment)."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query = parsed.query
    return f"{scheme}://{host}{path}{'?' + query if query else ''}"


def extract_additional_urls(*values: str) -> list[str]:
    urls = extract_urls(*values)
    return list(dict.fromkeys(urls))
