from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .auth import (
    WRITE_ROLES,
    create_session,
    create_user,
    delete_session,
    get_session_user,
    get_user_by_email,
    list_users as auth_list_users,
    update_user_role,
    verify_password,
)
from .config import settings
from .database import ensure_database, upsert_schedule
from .logging_config import setup_logging
from .models import (
    AuthRequest,
    AuthResponse,
    DiscoveryRequest,
    JobResponse,
    RoleUpdateRequest,
    ScheduleRequest,
    ScheduleResponse,
    SeedRequest,
    UserResponse,
)
from .service import job_manager

setup_logging()
logger = logging.getLogger(__name__)


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix):].strip() or None


def require_authenticated_user(token: Annotated[str | None, Depends(bearer_token)]) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def require_write_access(token: Annotated[str | None, Depends(bearer_token)]) -> dict:
    if settings.api_token and token == settings.api_token:
        return {
            "user_id": "api-token",
            "email": "api-token",
            "role": "admin",
            "status": "active",
            "created_at": "",
            "updated_at": "",
        }
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if user["role"] not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Your account can read, but cannot run jobs yet")
    return user


def require_admin_access(user: Annotated[dict, Depends(require_authenticated_user)]) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database()
    job_manager.start()
    try:
        yield
    finally:
        job_manager.stop()


app = FastAPI(title="Capstone Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "%s %s %s",
        request.method,
        request.url.path,
        response.status_code,
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "runs_dir": str(settings.runs_dir),
        "database_path": str(settings.database_path),
        "auth_enabled": True,
        "api_token_bypass_enabled": bool(settings.api_token),
        "session_auth_enabled": True,
        "cors_allow_origins": settings.cors_allow_origins or ["*"],
    }


@app.post("/api/auth/register", response_model=AuthResponse)
def register(request: AuthRequest) -> AuthResponse:
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if "@" not in request.email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    existing = get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = create_user(request.email, request.password)
    token = create_session(user["user_id"])
    return AuthResponse(token=token, user=UserResponse(**user))


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> AuthResponse:
    user_row = get_user_by_email(request.email)
    if not user_row or not verify_password(request.password, user_row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if user_row["status"] != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    user = {
        "user_id": user_row["user_id"],
        "email": user_row["email"],
        "role": user_row["role"],
        "status": user_row["status"],
        "created_at": user_row["created_at"],
        "updated_at": user_row["updated_at"],
    }
    token = create_session(user["user_id"])
    return AuthResponse(token=token, user=UserResponse(**user))


@app.post("/api/auth/logout", status_code=204)
def logout(token: Annotated[str | None, Depends(bearer_token)]) -> Response:
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    delete_session(token)
    return Response(status_code=204)


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: Annotated[dict, Depends(require_authenticated_user)]) -> UserResponse:
    return UserResponse(**user)


@app.get("/api/auth/users", response_model=list[UserResponse])
def list_users(_: Annotated[dict, Depends(require_admin_access)]) -> list[UserResponse]:
    return [UserResponse(**user) for user in auth_list_users()]


@app.post("/api/auth/users/{user_id}/role", response_model=UserResponse)
def set_user_role(
    user_id: str,
    request: RoleUpdateRequest,
    _: Annotated[dict, Depends(require_admin_access)],
) -> UserResponse:
    updated = update_user_role(user_id, request.role)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**updated)


@app.get("/api/incidents/latest/dashboard-view")
def latest_dashboard_view() -> dict:
    payload = job_manager.latest_dashboard_view()
    if not payload:
        raise HTTPException(status_code=404, detail="No dashboard run available yet")
    return payload


@app.get("/api/incidents/latest/augmented-incident")
def latest_augmented_incident() -> dict:
    payload = job_manager.latest_augmented_incident()
    if not payload:
        raise HTTPException(status_code=404, detail="No augmented incident available yet")
    return payload


@app.get("/api/incidents")
def list_incidents() -> dict:
    return {"incidents": job_manager.list_incidents()}


@app.get("/api/discovery/overview")
def get_discovery_overview() -> dict:
    return job_manager.get_discovery_overview()


@app.get("/api/incidents/{incident_id}")
def get_incident_bundle(incident_id: str) -> dict:
    payload = job_manager.get_incident_bundle(incident_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Incident not found")
    return payload


@app.get("/api/incidents/{incident_id}/analyst-report")
def get_analyst_report(incident_id: str) -> dict:
    payload = job_manager.get_analyst_report(incident_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Analyst report not found")
    return payload


# --- Run inspection endpoints (powers the redesigned /analyze/run/<id> view) ---

_DEMO_RUNS_DIR = Path(__file__).resolve().parent.parent / "site" / "demo-runs"
_FIXTURE_RUNS_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "runs"


def _resolve_run_dir(run_id: str) -> Path:
    """Resolve a run_id to an on-disk directory, preferring live runs/ then demo fixtures."""
    live = settings.runs_dir / run_id
    if live.exists() and live.is_dir():
        return live
    demo = _DEMO_RUNS_DIR / run_id
    if demo.exists() and demo.is_dir():
        return demo
    # Fixture runs: try exact, then fuzzy (all parts of run_id appear in dir name)
    if _FIXTURE_RUNS_DIR.exists():
        exact = _FIXTURE_RUNS_DIR / run_id
        if exact.exists():
            return exact
        parts = [p for p in run_id.split("-") if len(p) > 2]
        for d in sorted(_FIXTURE_RUNS_DIR.iterdir()):
            if d.is_dir() and all(p in d.name for p in parts):
                return d
    raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


@app.get("/api/runs/{run_id}/trace")
def get_run_trace(run_id: str) -> dict:
    run_dir = _resolve_run_dir(run_id)
    trace = _read_json(run_dir / "agent_trace.json") or {"incident_id": run_id, "agents": []}
    run_state = _read_json(run_dir / "run_state.json") or {}
    agents = trace.get("agents", [])

    # Compute elapsed_ms per agent (missing end => null).
    from datetime import datetime
    def _parse(ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    starts = [_parse(a.get("started_at")) for a in agents]
    ends = [_parse(a.get("completed_at")) for a in agents]
    run_started = min((t for t in starts if t), default=None)
    run_ended = max((t for t in ends if t), default=None)

    enriched = []
    for agent, start, end in zip(agents, starts, ends):
        elapsed_ms = int((end - start).total_seconds() * 1000) if start and end else None
        offset_ms = int((start - run_started).total_seconds() * 1000) if start and run_started else None
        enriched.append({**agent, "elapsed_ms": elapsed_ms, "offset_ms": offset_ms})

    return {
        "run_id": run_id,
        "incident_id": trace.get("incident_id", run_id),
        "agents": enriched,
        "run_started_at": run_started.isoformat() if run_started else None,
        "run_completed_at": run_ended.isoformat() if run_ended else None,
        "total_elapsed_ms": int((run_ended - run_started).total_seconds() * 1000) if run_started and run_ended else None,
        "current_stage": run_state.get("current_stage"),
        "node_status": run_state.get("node_status", {}),
    }


@app.get("/api/runs/{run_id}/sources")
def get_run_sources(run_id: str) -> dict:
    run_dir = _resolve_run_dir(run_id)
    index = _read_json(run_dir / "source_index.json") or {"sources": []}
    docs_payload = _read_json(run_dir / "source_documents.json") or {"documents": []}
    docs_by_id = {d.get("source_id"): d for d in docs_payload.get("documents", []) if d.get("source_id")}

    # Build tree nodes keyed by source_id, parent via `discovered_from`.
    nodes: dict[str, dict] = {}
    for src in index.get("sources", []):
        sid = src.get("source_id")
        if not sid:
            continue
        doc = docs_by_id.get(sid, {})
        nodes[sid] = {
            "source_id": sid,
            "url": src.get("url"),
            "source_type": src.get("source_type"),
            "depth": src.get("depth", 0),
            "priority": src.get("priority"),
            "fetch_status": src.get("fetch_status") or doc.get("fetch_status"),
            "discovered_from": src.get("discovered_from"),
            "title": doc.get("title"),
            "status_code": doc.get("status_code"),
            "fetched_at": doc.get("fetched_at"),
            "extracted_tx_count": len(doc.get("extracted_tx_hashes") or []),
            "extracted_address_count": len(doc.get("extracted_addresses") or []),
            "discovered_link_count": len(doc.get("discovered_links") or []),
            "children": [],
        }

    roots: list[dict] = []
    for sid, node in nodes.items():
        parent_id = node.get("discovered_from")
        if parent_id and parent_id in nodes and parent_id != sid:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    # Sort: by depth then priority desc
    def _sort(lst: list[dict]) -> None:
        lst.sort(key=lambda n: (n.get("depth", 0), -(n.get("priority") or 0)))
        for n in lst:
            _sort(n["children"])
    _sort(roots)

    from collections import Counter
    depth_counter = Counter(n["depth"] for n in nodes.values())

    return {
        "run_id": run_id,
        "stats": {
            "total": len(nodes),
            "seeds": depth_counter.get(0, 0),
            "depth_reached": max(depth_counter.keys(), default=0),
            "by_depth": dict(sorted(depth_counter.items())),
            "fetched": sum(1 for n in nodes.values() if n.get("fetch_status") == "fetched"),
        },
        "roots": roots,
    }


@app.get("/api/runs/{run_id}/report")
def get_run_report(run_id: str) -> dict:
    run_dir = _resolve_run_dir(run_id)
    return {
        "run_id": run_id,
        "dashboard_view": _read_json(run_dir / "dashboard_view.json"),
        "analyst_report": _read_json(run_dir / "analyst_report.json"),
        "augmented_incident": _read_json(run_dir / "augmented_incident.json"),
        "quality_report": _read_json(run_dir / "quality_report.json"),
        "contract_inventory": _read_json(run_dir / "contract_inventory.json"),
        "technical_analysis": _read_json(run_dir / "technical_analysis.json"),
        "pattern_hypotheses": _read_json(run_dir / "pattern_hypotheses.json"),
        "timeline": _read_json(run_dir / "timeline.json"),
    }


@app.get("/api/runs")
def list_runs() -> dict:
    """List all discoverable runs (live + demo) so the UI can populate a picker."""
    runs = []
    for base, tag in ((settings.runs_dir, "live"), (_DEMO_RUNS_DIR, "demo")):
        if not base.exists():
            continue
        for entry in sorted(base.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            trace = _read_json(entry / "agent_trace.json") or {}
            runs.append({
                "run_id": entry.name,
                "source": tag,
                "agent_count": len(trace.get("agents", [])),
                "has_report": (entry / "analyst_report.json").exists(),
            })
    return {"runs": runs}


@app.post("/api/jobs/augment", response_model=JobResponse)
def enqueue_augmentation(
    request: SeedRequest,
    _: dict = Depends(require_write_access),
) -> JobResponse:
    job_id = job_manager.enqueue_augmentation(request.model_dump(exclude_none=True))
    jobs = job_manager.list_jobs()
    row = next(job for job in jobs if job["job_id"] == job_id)
    return JobResponse(**row)


@app.post("/api/jobs/discovery", response_model=JobResponse)
def enqueue_discovery(
    request: DiscoveryRequest,
    _: dict = Depends(require_write_access),
) -> JobResponse:
    job_id = job_manager.enqueue_discovery(request.model_dump())
    jobs = job_manager.list_jobs()
    row = next(job for job in jobs if job["job_id"] == job_id)
    return JobResponse(**row)


@app.post("/api/jobs/demo-corpus", response_model=JobResponse)
def enqueue_demo_corpus(
    _: dict = Depends(require_write_access),
) -> JobResponse:
    job_id = job_manager.enqueue_demo_corpus()
    jobs = job_manager.list_jobs()
    row = next(job for job in jobs if job["job_id"] == job_id)
    return JobResponse(**row)


@app.get("/api/jobs/{job_id}/progress")
def get_job_progress(job_id: str) -> dict:
    jobs = job_manager.list_jobs()
    row = next((job for job in jobs if job["job_id"] == job_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result_run_dir = row.get("result_run_dir")
    stages: list[dict] = []
    current_stage: str | None = None
    detail: str | None = None

    progress_path = job_manager.job_progress_path(job_id)
    if progress_path.exists():
        progress_payload = json.loads(progress_path.read_text())
        current_stage = progress_payload.get("current_stage")
        stages = progress_payload.get("stages", [])
        detail = progress_payload.get("detail")

    if result_run_dir and not stages:
        run_state_path = Path(result_run_dir) / "run_state.json"
        if run_state_path.exists():
            run_state = json.loads(run_state_path.read_text())
            current_stage = run_state.get("current_stage")
            node_status: dict = run_state.get("node_status", {})
            stages = [{"name": name, "status": status} for name, status in node_status.items()]

    return {
        "job_id": job_id,
        "status": row["status"],
        "current_stage": current_stage,
        "stages": stages,
        "detail": detail,
    }


@app.get("/api/jobs", response_model=list[JobResponse])
def list_jobs(_: dict = Depends(require_write_access)) -> list[JobResponse]:
    return [JobResponse(**row) for row in job_manager.list_jobs()]


@app.post("/api/schedules/discovery", response_model=ScheduleResponse)
def configure_discovery_schedule(
    request: ScheduleRequest,
    _: dict = Depends(require_write_access),
) -> ScheduleResponse:
    status = "active" if request.enabled else "paused"
    upsert_schedule(
        schedule_name=request.schedule_name,
        job_type="discovery",
        status=status,
        interval_seconds=request.interval_seconds,
        payload=request.payload,
    )
    return ScheduleResponse(
        schedule_name=request.schedule_name,
        job_type="discovery",
        status=status,
        interval_seconds=request.interval_seconds,
        payload=request.payload,
        last_enqueued_at=None,
    )


@app.get("/api/schedules", response_model=list[ScheduleResponse])
def list_schedules(_: dict = Depends(require_write_access)) -> list[ScheduleResponse]:
    return [ScheduleResponse(**row) for row in job_manager.list_schedules()]
