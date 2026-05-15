from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SeedRequest(BaseModel):
    incident_id: str | None = None
    job_id: str | None = None
    trigger_type: str = "api"
    seed_type: str = "manual"
    chain: str
    protocol_name: str = ""
    incident_name: str = ""
    attack_tx_hashes: list[str] = Field(default_factory=list)
    attacker_addresses: list[str] = Field(default_factory=list)
    seed_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None

    @model_validator(mode="after")
    def validate_seed_signal(self) -> "SeedRequest":
        has_signal = any(
            [
                self.incident_id,
                self.seed_urls,
                self.attack_tx_hashes,
                self.attacker_addresses,
            ]
        )
        if not has_signal:
            raise ValueError(
                "Add at least one seed URL, attack transaction hash, attacker address, or existing incident ID."
            )
        return self


class DiscoveryRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["slowmist", "web3sec", "external_explorer", "defihacklabs"])
    seeds_dir: str = "runs/discovery_seeds"
    runs_dir: str = "runs"
    execute_augmentation: bool = True


class JobResponse(BaseModel):
    job_id: str
    incident_id: str | None
    job_type: str
    status: str
    seed_path: str | None = None
    result_run_dir: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class AuthRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    user_id: str
    email: str
    role: str
    status: str
    created_at: str
    updated_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class RoleUpdateRequest(BaseModel):
    role: Literal["viewer", "operator", "admin"]


class ScheduleRequest(BaseModel):
    schedule_name: str
    interval_seconds: int = 900
    enabled: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class ScheduleResponse(BaseModel):
    schedule_name: str
    job_type: str
    status: Literal["active", "paused"]
    interval_seconds: int
    payload: dict[str, Any]
    last_enqueued_at: str | None = None
