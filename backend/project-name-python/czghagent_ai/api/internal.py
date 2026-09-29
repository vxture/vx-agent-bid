# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-02
import asyncio
import base64
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from czghagent_ai.config import settings
from czghagent_ai.document_models import DocumentRenderRequest
from czghagent_ai.errors import ServiceError
from czghagent_ai.models import ParsedDocument
from czghagent_ai.services.ai_provider import (
    AiProviderAuthenticationError,
    AiProviderError,
    AiProviderNotConfiguredError,
    AiProviderTimeoutError,
    ConfigurableTenderAiProvider,
    OpenAiCompatibleProvider,
)
from czghagent_ai.services.atlas_endpoints import AUTHORIZED_ENDPOINT_CODES, routed_endpoint_codes
from czghagent_ai.services.atlas_provider import (
    AtlasNotEntitledError,
    AtlasProvider,
    AtlasTaskIdMissingError,
)
from czghagent_ai.services.document_parser import DocumentParserService
from czghagent_ai.services.document_qa import DocumentQaError
from czghagent_ai.services.document_renderer import DocumentRenderer
from czghagent_ai.services.file_readers import UnsupportedDocumentError
from czghagent_ai.services.structured_output import AiStructuredResult
from czghagent_ai.services.tender_ai import TenderAiService
from czghagent_ai.strategy_models import BidStrategyResponse
from czghagent_ai.tender_models import (
    AiResponseDiagnostics,
    AiResponseEnvelope,
    BranchBlueprint,
    BranchBlueprintRequest,
    ChapterDraftRequest,
    ChapterDraftResponse,
    InterpretationRequest,
    InterpretationResponse,
    OutlineAssemblyRequest,
    OutlineExpansionResponse,
    OutlineExpansionStageRequest,
    OutlineRequest,
    OutlineResponse,
    OutlineSkeletonPlan,
    OutlineSkeletonStageRequest,
    ProjectOverviewResponse,
    ReviewRequest,
    ReviewResponse,
    RevisionRequest,
    RevisionResponse,
    TechnicalScoringResponse,
)

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)
parser_service = DocumentParserService()
document_renderer = DocumentRenderer()
AiResponseData = TypeVar("AiResponseData", bound=BaseModel)


#: 部署态的判据。与 Java 侧的 DeployStage 保持同一套词。
_DEPLOYED_STAGES = frozenset({"dev", "beta", "production"})


def describe_model_exit() -> str:
    """本进程正在用哪个模型出口，一句话。

    刻意做成<b>返回字符串</b>而不是在装配时直接 log：装配发生在模块导入期，
    那时 uvicorn 还没配好日志，写出去的行谁也看不见。而这一行恰恰是这次
    改动最该被看见的事实——「产品跑得好好的，只是推理没进平台的账」
    是一种没有任何症状的偏差，日志是唯一的症状。
    """
    if settings.atlas_api_url:
        return (
            f"模型出口：Atlas {settings.atlas_api_url}"
            f"（按任务分走 {' / '.join(routed_endpoint_codes())}）"
        )
    if settings.deploy_stage in _DEPLOYED_STAGES:
        return (
            f"!!! 部署阶段 {settings.deploy_stage} 正在直连模型供应商："
            f"所有推理消耗都不入平台的账。这是显式开启的降级。"
        )
    return f"模型出口：直连 {settings.ai_model_base_url}（本地；推理消耗不入平台的账）"


def create_ai_provider() -> ConfigurableTenderAiProvider:
    """选出本次进程使用的模型出口。

    配了 ``ATLAS_API_URL`` 就走 Atlas——它是通则规定的<b>唯一</b>模型出口。
    没配则退回直连模型供应商，而这条路在部署态被<b>拒绝启动</b>。

    直连能跑通，而且跑得很好，这正是它危险的地方：整个产品一切正常，
    只是每一次推理都没有进平台的账。这种偏差不会有任何症状，
    只会在月底对量时表现为一个没人解释得了的缺口。所以它和身份、权益、
    用量上报的替身走同一条纪律：本地可用，部署态必须显式承认才允许。
    """
    if settings.atlas_api_url:
        return AtlasProvider(
            settings.atlas_api_url,
            timeout_seconds=settings.atlas_timeout_seconds,
            max_retries=settings.ai_model_max_retries,
        )
    if settings.deploy_stage in _DEPLOYED_STAGES and not settings.allow_mock_on_deploy:
        raise RuntimeError(
            f"部署阶段 {settings.deploy_stage} 缺少 ATLAS_API_URL，"
            "拒绝以直连模型供应商的方式启动——那条路会让所有推理消耗都不入平台的账。"
            "补齐配置或显式设置 ALLOW_MOCK_ON_DEPLOY=true（会自报降级）"
        )
    return OpenAiCompatibleProvider(
        settings.ai_model_api_key,
        settings.ai_model_base_url,
        settings.ai_model_name,
        settings.ai_model_timeout_seconds,
        settings.ai_model_max_retries,
        thinking_disabled_operations=settings.ai_model_thinking_disabled_operations,
        quality_model=settings.ai_model_quality_name,
        thinking_enabled_operations=settings.ai_model_thinking_enabled_operations,
        request_dialect=settings.ai_model_request_dialect,
        thinking_budget_tokens=settings.ai_model_thinking_budget_tokens,
    )


model_exit = create_ai_provider()
tender_ai_service = TenderAiService(model_exit)


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    """内部服务令牌校验。

    常量时间比较，且不区分「没带」与「带错」——两者返回同一个码，
    因为把它们分开只对攻击者有用。
    """
    if not secrets.compare_digest(x_internal_token, settings.internal_token):
        raise ServiceError(
            "AUTH_INTERNAL_TOKEN_INVALID", "内部服务令牌无效", 401, retryable=False
        )


@router.post("/parse", response_model=ParsedDocument, dependencies=[Depends(require_internal_token)])
async def parse_document(file: Annotated[UploadFile, File()]) -> ParsedDocument:
    content = await file.read()
    try:
        return await asyncio.to_thread(
            parser_service.parse, file.filename or "document", content
        )
    except UnsupportedDocumentError as exception:
        raise ServiceError(
            "PARSER_DOCUMENT_UNSUPPORTED", str(exception), 422, retryable=False
        ) from exception


def map_ai_error(exception: AiProviderError) -> ServiceError:
    """把模型侧失败翻成平台封套。

    ``exception.code`` 原样带出，不在这里重命名——被调方自己的码是调用方
    分支的依据，中途改名等于让上游那条分支永远不进。
    ``retryable`` 由错误码派生（见 :mod:`czghagent_ai.errors`）：
    配置缺失和结构化输出不合法都不会因为等一会儿而变好。
    """
    if isinstance(exception, AtlasNotEntitledError):
        # 503 而不是 403，码也刻意<b>不是</b>通则那个 NOT_ENTITLED。
        # 那个码的含义是「这个用户/工作空间没买」，会被上游渲染成一句
        # 「请先订阅」——而这里的真相是运营侧漏了一条 Atlas endpoint 授权，
        # 跟用户买没买毫无关系。把两者混成一个码，会让所有人朝错误的方向查。
        status = 503
    elif isinstance(exception, AtlasTaskIdMissingError):
        # 链路自身的缺陷，不是模型侧的问题，也不会因为重试变好。
        status = 500
    elif isinstance(exception, AiProviderNotConfiguredError | AiProviderAuthenticationError):
        status = 503
    elif isinstance(exception, AiProviderTimeoutError):
        status = 504
    else:
        status = 502
    return ServiceError(
        exception.code, str(exception), status, details=exception.details()
    )


AiStageResult = TypeVar("AiStageResult")


async def run_ai_stage(
    stage: str, action: Callable[[], Awaitable[AiStageResult]]
) -> AiStageResult:
    """
    Execute one bounded AI stage and attach safe timing diagnostics.

    Preconditions:
        - action performs one independently retryable model-owned stage.
    Side Effects:
        - Calls the configured provider and emits metadata-only stage logs.
    Error Semantics:
        - AiProviderTimeoutError: the total Python stage deadline elapsed.
        - AiProviderError: provider, authentication, or structured output failure.
    """
    started = time.monotonic()
    logger.info("ai_stage_started", extra={"ai_stage": stage})
    try:
        async with asyncio.timeout(settings.ai_model_stage_timeout_seconds):
            result = await action()
    except TimeoutError as exception:
        elapsed = round((time.monotonic() - started) * 1000)
        logger.warning(
            "ai_stage_timed_out",
            extra={"ai_stage": stage, "elapsed_millis": elapsed},
        )
        raise AiProviderTimeoutError(
            "AI model stage timed out",
            stage=stage,
            elapsed_millis=elapsed,
        ) from exception
    except AiProviderError as exception:
        elapsed = round((time.monotonic() - started) * 1000)
        logger.warning(
            "ai_stage_failed",
            extra={
                "ai_stage": stage,
                "elapsed_millis": elapsed,
                "error_code": exception.code,
            },
        )
        raise exception.with_context(stage, elapsed) from exception
    elapsed = round((time.monotonic() - started) * 1000)
    logger.info(
        "ai_stage_completed",
        extra={"ai_stage": stage, "elapsed_millis": elapsed},
    )
    return result


def ai_envelope(
    result: AiStructuredResult[AiResponseData],
) -> AiResponseEnvelope[AiResponseData]:
    diagnostics = result.diagnostics
    return AiResponseEnvelope(
        data=result.data,
        diagnostics=AiResponseDiagnostics(
            finish_reason=diagnostics.finish_reason,
            response_length=diagnostics.response_length,
            response_hash=diagnostics.response_hash,
            input_tokens=diagnostics.input_tokens,
            output_tokens=diagnostics.output_tokens,
            reasoning_tokens=diagnostics.reasoning_tokens,
            cached_input_tokens=diagnostics.cached_input_tokens,
            attempts=result.attempts,
        ),
    )


@router.post(
    "/tender/interpretation/project-overview",
    response_model=AiResponseEnvelope[ProjectOverviewResponse],
    dependencies=[Depends(require_internal_token)],
)
async def extract_project_overview(
    body: InterpretationRequest,
) -> AiResponseEnvelope[ProjectOverviewResponse]:
    try:
        result = await run_ai_stage(
            "project_overview",
            lambda: tender_ai_service.extract_project_overview_result(body),
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/interpretation/technical-scoring",
    response_model=AiResponseEnvelope[TechnicalScoringResponse],
    dependencies=[Depends(require_internal_token)],
)
async def extract_technical_scoring(
    body: InterpretationRequest,
) -> AiResponseEnvelope[TechnicalScoringResponse]:
    try:
        result = await run_ai_stage(
            "technical_scoring",
            lambda: tender_ai_service.extract_technical_scoring_result(body),
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/interpretation",
    response_model=InterpretationResponse,
    dependencies=[Depends(require_internal_token)],
)
async def interpret_tender(body: InterpretationRequest) -> InterpretationResponse:
    try:
        return await run_ai_stage("interpretation", lambda: tender_ai_service.interpret(body))
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/outline",
    response_model=AiResponseEnvelope[OutlineResponse],
    dependencies=[Depends(require_internal_token)],
)
async def plan_outline(body: OutlineRequest) -> AiResponseEnvelope[OutlineResponse]:
    try:
        result = await run_ai_stage(
            "outline_legacy", lambda: tender_ai_service.outline_result(body)
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/outline/strategy",
    response_model=AiResponseEnvelope[BidStrategyResponse],
    dependencies=[Depends(require_internal_token)],
)
async def plan_outline_strategy(
    body: OutlineRequest,
) -> AiResponseEnvelope[BidStrategyResponse]:
    try:
        result = await run_ai_stage(
            "outline_strategy",
            lambda: tender_ai_service.outline_strategy_result(body),
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/outline/skeleton",
    response_model=AiResponseEnvelope[OutlineSkeletonPlan],
    dependencies=[Depends(require_internal_token)],
)
async def plan_outline_skeleton(
    body: OutlineSkeletonStageRequest,
) -> AiResponseEnvelope[OutlineSkeletonPlan]:
    try:
        result = await run_ai_stage(
            "outline_skeleton",
            lambda: tender_ai_service.outline_skeleton_result(body),
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/outline/expansion",
    response_model=AiResponseEnvelope[OutlineExpansionResponse],
    dependencies=[Depends(require_internal_token)],
)
async def expand_outline_branch(
    body: OutlineExpansionStageRequest,
) -> AiResponseEnvelope[OutlineExpansionResponse]:
    try:
        result = await run_ai_stage(
            f"outline_expansion_{body.batch_index}",
            lambda: tender_ai_service.outline_expansion_result(body),
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/outline/assemble",
    response_model=OutlineResponse,
    dependencies=[Depends(require_internal_token)],
)
async def assemble_outline(body: OutlineAssemblyRequest) -> OutlineResponse:
    try:
        return tender_ai_service.assemble_outline(body)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/chapter/blueprint",
    response_model=AiResponseEnvelope[BranchBlueprint],
    dependencies=[Depends(require_internal_token)],
)
async def plan_branch_blueprint(
    body: BranchBlueprintRequest,
) -> AiResponseEnvelope[BranchBlueprint]:
    try:
        result = await run_ai_stage(
            "branch_blueprint",
            lambda: tender_ai_service.plan_branch_blueprint_result(body),
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/chapter",
    response_model=AiResponseEnvelope[ChapterDraftResponse],
    dependencies=[Depends(require_internal_token)],
)
async def draft_chapter(body: ChapterDraftRequest) -> AiResponseEnvelope[ChapterDraftResponse]:
    try:
        result = await run_ai_stage(
            "chapter", lambda: tender_ai_service.draft_result(body)
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/revision",
    response_model=AiResponseEnvelope[RevisionResponse],
    dependencies=[Depends(require_internal_token)],
)
async def revise_section(body: RevisionRequest) -> AiResponseEnvelope[RevisionResponse]:
    try:
        result = await run_ai_stage(
            "revision", lambda: tender_ai_service.revise_result(body)
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/review",
    response_model=AiResponseEnvelope[ReviewResponse],
    dependencies=[Depends(require_internal_token)],
)
async def review_bid(body: ReviewRequest) -> AiResponseEnvelope[ReviewResponse]:
    try:
        result = await run_ai_stage(
            "review", lambda: tender_ai_service.review_result(body)
        )
        return ai_envelope(result)
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception


@router.post(
    "/tender/document/render",
    dependencies=[Depends(require_internal_token)],
    response_class=Response,
)
async def render_tender_document(body: DocumentRenderRequest) -> Response:
    try:
        content, qa = await asyncio.to_thread(document_renderer.render, body)
    except ValueError as exception:
        raise ServiceError(
            "DOCUMENT_RENDER_CONFLICT", str(exception), 409, retryable=False
        ) from exception
    except DocumentQaError as exception:
        raise ServiceError(
            "DOCUMENT_RENDER_FAILED", str(exception), 502, retryable=True
        ) from exception
    encoded_summary = base64.urlsafe_b64encode(qa.summary.encode("utf-8")).decode("ascii")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": 'attachment; filename="tender.docx"',
            "X-Actual-Pages": "" if qa.actual_pages is None else str(qa.actual_pages),
            "X-QA-Status": qa.status,
            "X-QA-Summary-Base64": encoded_summary,
        },
    )


# ── 系统验证：Atlas 探测 ─────────────────────────────────────────────────────
#
# 票由 Java 侧现铸并随请求头转呈，与业务调用同一条链：这两个端点证明的是
# 「本产品的模型调用能走通」，而不是「某条专门的诊断线路能走通」。


class AtlasProbeRequest(BaseModel):
    """要探测的路由；不送则逐条探测本产品真正会调用的路由。"""

    endpointCodes: list[str] | None = None  # 线上契约是 camelCase


def _atlas_exit() -> AtlasProvider:
    if not isinstance(model_exit, AtlasProvider):
        raise ServiceError(
            "AI_ATLAS_NOT_CONFIGURED",
            "本进程没有走 Atlas：ATLAS_API_URL 未配置，模型调用正在直连供应商",
            503,
            retryable=False,
        )
    return model_exit


@router.get("/atlas/models", dependencies=[Depends(require_internal_token)])
async def list_atlas_models() -> dict[str, object]:
    """带票读 Atlas 的模型清单。不计量。"""
    try:
        codes = await _atlas_exit().list_models()
    except AiProviderError as exception:
        raise map_ai_error(exception) from exception
    return {"count": len(codes), "models": codes}


@router.post("/atlas/probe", dependencies=[Depends(require_internal_token)])
async def probe_atlas(body: AtlasProbeRequest) -> dict[str, object]:
    """对每条路由各发一次最短的真实调用。<b>会花钱</b>，由 Atlas 自行计量。

    只接受授权清单里的路由：这是一个会花钱的端点，不能让它变成
    「随便挑一个 code 打一次」的通道。逐条顺序执行——并发只省几秒，
    却会让同一个 task_id 下的几笔消耗在 Atlas 日志里交错。
    """
    provider = _atlas_exit()
    codes = body.endpointCodes or list(routed_endpoint_codes())
    unknown = sorted(set(codes) - AUTHORIZED_ENDPOINT_CODES)
    if unknown:
        raise ServiceError(
            "AI_ATLAS_ENDPOINT_NOT_AUTHORIZED",
            f"不在本产品的 Atlas 授权清单里：{', '.join(unknown)}",
            422,
            retryable=False,
        )
    return {"results": [await provider.probe(code) for code in codes]}
