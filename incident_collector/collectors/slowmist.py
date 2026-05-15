from __future__ import annotations

import logging
import time

import requests
from bs4 import BeautifulSoup

from incident_collector.collectors.base import BaseCollector
from incident_collector.models import IncidentRecord
from incident_collector.utils import (
    absolutize,
    guess_chain,
    normalize_attack_type,
    parse_date,
    within_date_range,
)

logger = logging.getLogger(__name__)


class SlowMistCollector(BaseCollector):
    source_name = "SlowMist"
    base_url = "https://hacked.slowmist.io/"
    page_limit = 150

    def collect(self) -> list[IncidentRecord]:
        records: list[IncidentRecord] = []
        for page in range(1, self.page_limit + 1):
            url = f"{self.base_url}?c=&page={page}"
            _t = time.perf_counter()
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning(
                    "collector.fetch_failed",
                    extra={"source": self.source_name, "url": url, "page": page, "error": str(exc)},
                )
                break
            duration_ms = round((time.perf_counter() - _t) * 1000)
            soup = BeautifulSoup(response.text, "lxml")
            entries = soup.select("div.case-content > ul > li")
            if not entries:
                logger.info("collector.page_empty", extra={"source": self.source_name, "page": page})
                break

            page_records = 0
            for entry in entries:
                record = self._parse_entry(entry)
                if not record:
                    continue
                if within_date_range(
                    record.incident_date, self.config.start_date, self.config.end_date
                ):
                    records.append(record)
                    page_records += 1

            logger.debug(
                "collector.page_fetched",
                extra={"source": self.source_name, "page": page, "page_records": page_records, "duration_ms": duration_ms},
            )

            earliest = self._page_earliest_date(entries)
            if (
                earliest
                and self.config.start_date
                and earliest < self.config.start_date
                and page_records == 0
            ):
                break

        logger.info("collector.completed", extra={"source": self.source_name, "total_records": len(records)})
        return records

    def _parse_entry(self, entry) -> IncidentRecord | None:
        time_tag = entry.select_one("span.time")
        title_tag = entry.select_one("h3")
        description_tags = entry.find_all("p")
        if not time_tag or not title_tag or len(description_tags) < 2:
            return None

        incident_date = parse_date(time_tag.get_text(strip=True))
        project_name = title_tag.get_text(" ", strip=True).replace("Hacked target:", "").strip()
        description = description_tags[0].get_text(" ", strip=True).replace(
            "Description of the event:", ""
        ).strip()
        meta_text = description_tags[1].get_text(" ", strip=True)
        loss_text = meta_text.split("Attack method:")[0].replace("Amount of loss:", "").strip()
        attack_method = ""
        if "Attack method:" in meta_text:
            attack_method = meta_text.split("Attack method:", 1)[1].strip()

        link_tag = entry.select_one("p.link-reference a[href]")
        source_url = absolutize(self.base_url, link_tag["href"]) if link_tag else self.base_url

        chain = guess_chain(project_name, description, attack_method)
        normalized = normalize_attack_type(description, attack_method)
        tags = [tag for tag in [chain.lower() if chain else "", normalized] if tag]

        return IncidentRecord(
            incident_date=incident_date,
            source_name=self.source_name,
            source_url=source_url,
            project_name=project_name,
            chain=chain,
            attack_type_raw=attack_method,
            attack_type_normalized=normalized,
            loss_text=loss_text,
            summary=description,
            notes=description,
            tags=tags,
        )

    def _page_earliest_date(self, entries) -> object:
        dates = []
        for entry in entries:
            tag = entry.select_one("span.time")
            if not tag:
                continue
            dates.append(parse_date(tag.get_text(strip=True)))
        return min(dates) if dates else None

