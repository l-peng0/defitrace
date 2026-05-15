from __future__ import annotations

import base64
import logging
import re
import time

import requests

from incident_collector.collectors.base import BaseCollector
from incident_collector.models import IncidentRecord
from incident_collector.utils import guess_chain, month_bounds, month_range, normalize_attack_type, within_date_range

logger = logging.getLogger(__name__)


class DeFiHackLabsCollector(BaseCollector):
    source_name = "DeFiHackLabs"
    api_base = "https://api.github.com/repos/SunWeb3Sec/DeFiHackLabs/contents"
    request_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "capstone-incident-collector",
    }

    def collect(self) -> list[IncidentRecord]:
        if self.config.start_date and self.config.end_date:
            months = month_range(self.config.start_date, self.config.end_date)
        else:
            months = self._list_available_months()

        records: list[IncidentRecord] = []
        for month in months:
            month_start, _ = month_bounds(month)
            if not within_date_range(month_start, self.config.start_date, self.config.end_date):
                continue

            url = f"{self.api_base}/src/test/{month}?ref=main"
            _t = time.perf_counter()
            try:
                response = requests.get(url, headers=self.request_headers, timeout=30)
                if response.status_code == 404:
                    logger.debug("collector.month_not_found", extra={"source": self.source_name, "month": month})
                    continue
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning(
                    "collector.fetch_failed",
                    extra={"source": self.source_name, "url": url, "month": month, "error": str(exc)},
                )
                continue
            duration_ms = round((time.perf_counter() - _t) * 1000)

            month_records = 0
            for item in response.json():
                if item.get("type") != "file" or not item["name"].endswith(".sol"):
                    continue
                record = self._parse_file(month_start, item)
                if record and within_date_range(
                    record.incident_date, self.config.start_date, self.config.end_date
                ):
                    records.append(record)
                    month_records += 1

            logger.debug(
                "collector.month_fetched",
                extra={"source": self.source_name, "month": month, "month_records": month_records, "duration_ms": duration_ms},
            )

        logger.info("collector.completed", extra={"source": self.source_name, "total_records": len(records)})
        return records

    def _list_available_months(self) -> list[str]:
        url = f"{self.api_base}/src/test?ref=main"
        response = requests.get(url, headers=self.request_headers, timeout=30)
        response.raise_for_status()
        months: list[str] = []
        for item in response.json():
            if item.get("type") != "dir":
                continue
            name = item.get("name", "")
            if re.fullmatch(r"\d{4}-\d{2}", name):
                months.append(name)
        months.sort()
        return months

    def _parse_file(self, incident_date, item: dict) -> IncidentRecord | None:
        content = self._fetch_file_content(item["url"])
        if not content:
            return None

        file_name = item["name"]
        project_name = file_name.replace("_exp.sol", "").replace(".sol", "")
        chain = guess_chain(file_name, content)
        normalized = normalize_attack_type(file_name, content)

        notes = self._extract_interesting_lines(content)
        summary = notes.splitlines()[0] if notes else f"PoC file for {project_name}"

        return IncidentRecord(
            incident_date=incident_date,
            source_name=self.source_name,
            source_url=item.get("html_url", api_url_to_html_url(item["url"])),
            project_name=project_name,
            chain=chain,
            attack_type_raw=self._extract_attack_hint(content),
            attack_type_normalized=normalized,
            attack_tx_url=self._extract_tx_url(content),
            attack_contract_url=self._extract_address_url(content),
            victim_contract_url="",
            loss_text="",
            summary=summary,
            notes=notes,
            tags=[tag for tag in [month_tag(incident_date), chain.lower() if chain else "", normalized] if tag],
        )

    def _fetch_file_content(self, api_url: str) -> str:
        for attempt in range(3):
            response = requests.get(api_url, headers=self.request_headers, timeout=30)
            if response.status_code in {403, 429}:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            encoded = payload.get("content", "")
            if not encoded:
                return ""
            return base64.b64decode(encoded).decode("utf-8", errors="replace")
        return ""

    def _extract_interesting_lines(self, content: str) -> str:
        lines: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.strip().lstrip("/").strip()
            if not line:
                continue
            if any(
                marker in line.lower()
                for marker in [
                    "tx",
                    "attack",
                    "hack",
                    "vuln",
                    "flashloan",
                    "price",
                    "oracle",
                    "loss",
                    "exploit",
                ]
            ):
                lines.append(line)
            if len(lines) >= 8:
                break
        return "\n".join(lines)

    def _extract_attack_hint(self, content: str) -> str:
        notes = self._extract_interesting_lines(content).lower()
        if "oracle" in notes and "manip" in notes:
            return "oracle manipulation"
        if "price" in notes and "manip" in notes:
            return "price manipulation"
        if "flashloan" in notes:
            return "flashloan-assisted exploit"
        return ""

    def _extract_tx_url(self, content: str) -> str:
        patterns = [
            r"https?://[^\s)\"'>]*/tx/[^\s)\"'>]+",
            r"https?://[^\s)\"'>]*/explorer/tx/[^\s)\"'>]+",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return ""

    def _extract_address_url(self, content: str) -> str:
        match = re.search(r"https?://[^\s)\"'>]*/address/[^\s)\"'>]+", content, flags=re.IGNORECASE)
        return match.group(0) if match else ""


def month_tag(incident_date) -> str:
    return incident_date.strftime("%Y-%m")


def api_url_to_html_url(api_url: str) -> str:
    return api_url.replace(
        "https://api.github.com/repos/SunWeb3Sec/DeFiHackLabs/contents/",
        "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/",
    ).replace("?ref=main", "")
