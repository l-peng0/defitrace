from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from typing import Iterable
from urllib.parse import urljoin


CHAIN_KEYWORDS = {
    "ethereum": "Ethereum",
    "eth": "Ethereum",
    "bsc": "BSC",
    "binance smart chain": "BSC",
    "arbitrum": "Arbitrum",
    "base": "Base",
    "optimism": "Optimism",
    "polygon": "Polygon",
    "avalanche": "Avalanche",
    "solana": "Solana",
    "tron": "Tron",
    "blast": "Blast",
}


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def month_range(start: date, end: date) -> list[str]:
    current_year = start.year
    current_month = start.month
    months: list[str] = []
    while (current_year, current_month) <= (end.year, end.month):
        months.append(f"{current_year:04d}-{current_month:02d}")
        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1
    return months


def month_bounds(month_string: str) -> tuple[date, date]:
    year, month = [int(piece) for piece in month_string.split("-")]
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def within_date_range(value: date, start: date | None, end: date | None) -> bool:
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


def guess_chain(*values: str) -> str:
    combined = " ".join(value.lower() for value in values if value)
    for needle, chain in CHAIN_KEYWORDS.items():
        if re.search(rf"\b{re.escape(needle)}\b", combined):
            return chain
    return ""


def normalize_attack_type(*values: str) -> str:
    combined = " ".join(value.lower() for value in values if value)
    if "price manipulation" in combined:
        return "price_manipulation"
    if "oracle" in combined and "manipulation" in combined:
        return "oracle_manipulation"
    if "flash loan" in combined and (
        "manipulation" in combined or "reserve" in combined
    ):
        return "price_manipulation"
    return ""


def extract_urls(*values: str) -> list[str]:
    urls: list[str] = []
    for value in values:
        if not value:
            continue
        urls.extend(re.findall(r"https?://[^\s)\"'>]+", value))
    return urls


def first_url_matching(patterns: Iterable[str], *values: str) -> str:
    urls = extract_urls(*values)
    for pattern in patterns:
        for url in urls:
            if pattern in url:
                return url
    return urls[0] if urls else ""


def absolutize(base_url: str, url: str) -> str:
    return urljoin(base_url, url)

