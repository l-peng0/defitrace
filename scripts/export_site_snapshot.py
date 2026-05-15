from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.service import job_manager


SITE_DATA = ROOT / "site" / "data"
INCIDENT_DIR = SITE_DATA / "incidents"


def main() -> int:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)

    incidents = job_manager.list_incidents()
    (SITE_DATA / "live_incident_library.json").write_text(
        json.dumps({"incidents": incidents}, indent=2, ensure_ascii=True) + "\n"
    )

    for incident in incidents:
        bundle = job_manager.get_incident_bundle(incident["incident_id"])
        if not bundle:
            continue
        (INCIDENT_DIR / f"{incident['incident_id']}.json").write_text(
            json.dumps(bundle, indent=2, ensure_ascii=True) + "\n"
        )

    latest_dashboard = job_manager.latest_dashboard_view()
    if latest_dashboard:
        (SITE_DATA / "dashboard_view.json").write_text(
            json.dumps(latest_dashboard, indent=2, ensure_ascii=True) + "\n"
        )

    latest_augmented = job_manager.latest_augmented_incident()
    if latest_augmented:
        (SITE_DATA / "augmented_incident.json").write_text(
            json.dumps(latest_augmented, indent=2, ensure_ascii=True) + "\n"
        )

    print(
        json.dumps(
            {
                "incident_count": len(incidents),
                "library_path": str(SITE_DATA / "live_incident_library.json"),
                "incident_dir": str(INCIDENT_DIR),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
