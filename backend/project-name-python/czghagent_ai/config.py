# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-02
import os
from dataclasses import dataclass

from czghagent_ai.model_config import AiModelRequestDialect

DEFAULT_THINKING_DISABLED_OPERATIONS = (
    "project_overview_source_selection,project_overview_extraction,"
    "technical_scoring_extraction,outline_skeleton_planning,"
    "outline_branch_expansion,chapter_drafting"
)
DEFAULT_THINKING_ENABLED_OPERATIONS = (
    "bid_strategy_planning,branch_blueprint_planning,section_revision,consistency_review"
)


@dataclass(frozen=True)
class Settings:
    internal_token: str
    deploy_stage: str
    allow_mock_on_deploy: bool
    atlas_api_url: str
    ai_model_api_key: str
    ai_model_base_url: str
    ai_model_request_dialect: AiModelRequestDialect
    ai_model_name: str
    ai_model_quality_name: str
    ai_model_timeout_seconds: float
    ai_model_stage_timeout_seconds: float
    ai_model_max_retries: int
    ai_model_thinking_budget_tokens: int
    ai_model_thinking_disabled_operations: frozenset[str]
    ai_model_thinking_enabled_operations: frozenset[str]

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            internal_token=os.getenv("AI_SERVICE_INTERNAL_TOKEN", "local-development-token"),
            deploy_stage=os.getenv("DEPLOY_STAGE", "local").strip().lower(),
            allow_mock_on_deploy=os.getenv("ALLOW_MOCK_ON_DEPLOY", "").strip().lower()
            in {"1", "true", "yes"},
            atlas_api_url=os.getenv("ATLAS_API_URL", "").strip(),
            ai_model_api_key=os.getenv("AI_MODEL_API_KEY", "").strip(),
            ai_model_base_url=os.getenv(
                "AI_MODEL_BASE_URL", "https://api.deepseek.com"
            ),
            ai_model_request_dialect=AiModelRequestDialect.parse(
                os.getenv("AI_MODEL_REQUEST_DIALECT", "deepseek")
            ),
            ai_model_name=os.getenv(
                "AI_MODEL_FAST_NAME",
                os.getenv("AI_MODEL_NAME", "deepseek-v4-flash"),
            ),
            ai_model_quality_name=os.getenv(
                "AI_MODEL_QUALITY_NAME", "deepseek-v4-pro"
            ),
            ai_model_timeout_seconds=float(
                os.getenv("AI_MODEL_TIMEOUT_SECONDS", "240")
            ),
            ai_model_stage_timeout_seconds=float(
                os.getenv("AI_MODEL_STAGE_TIMEOUT_SECONDS", "540")
            ),
            ai_model_max_retries=int(os.getenv("AI_MODEL_MAX_RETRIES", "1")),
            ai_model_thinking_budget_tokens=int(
                os.getenv("AI_MODEL_THINKING_BUDGET_TOKENS", "4096")
            ),
            ai_model_thinking_disabled_operations=frozenset(
                operation.strip()
                for operation in os.getenv(
                    "AI_MODEL_THINKING_DISABLED_OPERATIONS",
                    DEFAULT_THINKING_DISABLED_OPERATIONS,
                ).split(",")
                if operation.strip()
            ),
            ai_model_thinking_enabled_operations=frozenset(
                operation.strip()
                for operation in os.getenv(
                    "AI_MODEL_THINKING_ENABLED_OPERATIONS",
                    DEFAULT_THINKING_ENABLED_OPERATIONS,
                ).split(",")
                if operation.strip()
            ),
        )


settings = Settings.from_environment()
