"""End-to-end demo check: open live site, select Paribus case, screenshot report."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

LIVE = "http://52.76.84.172/"
INCIDENT_ID = "paribus-arbitrum-2025-01-18"
OUT = Path(__file__).resolve().parent.parent / "runs" / "_e2e_demo"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(LIVE, wait_until="networkidle", timeout=30_000)
        page.screenshot(path=str(OUT / "01_landing.png"), full_page=True)

        page.wait_for_selector("#incident-list .incident-row", timeout=20_000)
        card = page.locator("#incident-list .incident-row", has_text="Paribus").first
        card.wait_for(timeout=10_000)
        card.click()

        page.wait_for_function(
            "document.querySelector('#hero-title')?.textContent?.toLowerCase().includes('paribus')",
            timeout=15_000,
        )
        page.screenshot(path=str(OUT / "02_paribus_report.png"), full_page=True)

        hero = page.locator("#hero-title").inner_text()
        sources = page.locator("#hero-source-count").inner_text()
        ready = page.locator("#hero-completeness").inner_text()

        browser.close()

        print(f"hero_title={hero!r}  sources={sources}  ready={ready}")
        if errors:
            print("PAGE ERRORS:", *errors, sep="\n  ")
            return 1
        print(f"screenshots -> {OUT}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
