from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from openai import APIError, OpenAI

logger = logging.getLogger(__name__)

MAX_TOKENS = 8192
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class ModelConfig:
    model: str
    api_key_env: str
    base_url: str | None = None

    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


STAGE_MODEL_CHAIN: dict[str, list[ModelConfig]] = {
    "llm_evidence_extractor": [
        ModelConfig(model="glm-5-turbo", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1-mini", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
    "llm_timeline_synthesizer": [
        ModelConfig(model="glm-5-turbo", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1-mini", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
    "llm_narrative_writer": [
        ModelConfig(model="glm-5", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
    "llm_quality_assessor": [
        ModelConfig(model="glm-5", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
    "technical_reasoner": [
        ModelConfig(model="glm-5", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="glm-5-turbo", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
    "technical_reasoner_json_repair": [
        ModelConfig(model="glm-5", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="glm-4-plus", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
    "technical_reasoner_revision": [
        ModelConfig(model="glm-5", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="glm-5-turbo", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
        ModelConfig(model="openai/gpt-4.1", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
    ],
}

_DEFAULT_CHAIN = [
    ModelConfig(model="glm-5-turbo", api_key_env="GLM_API_KEY", base_url=GLM_BASE_URL),
    ModelConfig(model="openai/gpt-4.1-mini", api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL),
]


def call_llm_with_metadata(
    system_prompt: str,
    user_prompt: str,
    incident_id: str,
    stage_name: str,
) -> dict[str, Any]:
    chain = STAGE_MODEL_CHAIN.get(stage_name, _DEFAULT_CHAIN)
    last_exc: Exception | None = None

    for config in chain:
        api_key = config.api_key()
        if not api_key:
            logger.warning(
                "llm.no_api_key",
                extra={"stage": stage_name, "model": config.model, "env": config.api_key_env},
            )
            continue

        client = OpenAI(api_key=api_key, base_url=config.base_url)
        start = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=config.model,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            duration_ms = round((time.perf_counter() - start) * 1000)
            usage = response.usage
            logger.info(
                "llm.call_completed",
                extra={
                    "incident_id": incident_id,
                    "stage": stage_name,
                    "model": config.model,
                    "input_tokens": usage.prompt_tokens if usage else 0,
                    "output_tokens": usage.completion_tokens if usage else 0,
                    "duration_ms": duration_ms,
                },
            )
            content = response.choices[0].message.content or ""
            if not content.strip():
                logger.warning(
                    "llm.empty_response_trying_next",
                    extra={
                        "incident_id": incident_id,
                        "stage": stage_name,
                        "model": config.model,
                    },
                )
                continue
            return {
                "content": content,
                "model": config.model,
                "api_key_env": config.api_key_env,
                "base_url": config.base_url or "",
            }
        except APIError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000)
            logger.warning(
                "llm.model_failed_trying_next",
                extra={
                    "stage": stage_name,
                    "model": config.model,
                    "error": str(exc),
                    "duration_ms": duration_ms,
                },
            )
            last_exc = exc

    if last_exc:
        raise last_exc
    raise APIError(message="No API key configured for any model in chain", request=None, body=None)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    incident_id: str,
    stage_name: str,
) -> str:
    return call_llm_with_metadata(system_prompt, user_prompt, incident_id, stage_name)["content"]
