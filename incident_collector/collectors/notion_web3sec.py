from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime

from playwright.async_api import async_playwright

from incident_collector.collectors.base import BaseCollector
from incident_collector.models import IncidentRecord
from incident_collector.utils import within_date_range

logger = logging.getLogger(__name__)


class Web3SecNotionCollector(BaseCollector):
    source_name = "Web3Sec Notion"
    url = "https://web3sec.notion.site/c582b99cd7a84be48d972ca2126a2a1f?v=4671590619bd4b2ab16a15256e4fbba1"

    def collect(self) -> list[IncidentRecord]:
        logger.info("collector.started", extra={"source": self.source_name, "url": self.url})
        _t = time.perf_counter()
        records = asyncio.run(self._collect_async())
        logger.info("collector.completed", extra={"source": self.source_name, "total_records": len(records), "duration_ms": round((time.perf_counter() - _t) * 1000)})
        return records

    async def _collect_async(self) -> list[IncidentRecord]:
        lines = await self._fetch_lines_with_retries()
        records: list[IncidentRecord] = []
        seen_keys: set[tuple[str, str]] = set()
        for index, line in enumerate(lines[:-4]):
            if not re.fullmatch(r"\d{8}", line):
                continue

            incident_date = datetime.strptime(line, "%Y%m%d").date()
            if not within_date_range(
                incident_date, self.config.start_date, self.config.end_date
            ):
                continue

            previous_window = lines[max(0, index - 3) : index]
            if "Price Manipulation" not in previous_window:
                continue

            project_name = lines[index + 1]
            root_cause = lines[index + 2]
            loss_text = lines[index + 3]
            poc_url = lines[index + 4] if lines[index + 4].startswith("http") else self.url
            key = (incident_date.isoformat(), project_name.lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)

            records.append(
                IncidentRecord(
                    incident_date=incident_date,
                    source_name=self.source_name,
                    source_url=self.url,
                    project_name=project_name,
                    chain="",
                    attack_type_raw="Price Manipulation",
                    attack_type_normalized="price_manipulation",
                    loss_text=loss_text,
                    summary=f"{project_name} | {root_cause} | {loss_text}",
                    notes=f"Root cause: {root_cause}\nPOC: {poc_url}",
                    tags=["price_manipulation"],
                )
            )
        return records

    async def _fetch_lines_with_retries(self) -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 2400})
            try:
                for _ in range(5):
                    await page.goto(self.url, wait_until="domcontentloaded", timeout=120000)
                    await page.wait_for_timeout(8000)
                    text = await page.inner_text("body")
                    if len(text) > 1000 and "DeFi Hacks Analysis - Root Cause Analysis" in text:
                        return [line.strip() for line in text.splitlines() if line.strip()]
                return []
            finally:
                await browser.close()
