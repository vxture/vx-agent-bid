# GENERATED_BY_AI
# MODEL: claude-opus-5
# DATE: 2026-09-15
"""内部接口的失败路径：模型出口怎么选、每种失败翻成什么码与状态、每个端点都接上了翻译。

Java 侧按 ``code`` 与 ``retryable`` 分支。这里错一格的表现都不是报错：
配置缺失被标成可重试，上游就会对一个永远不会好的请求重试到超时；
授权漏配被标成「未订阅」，所有人就朝用户侧去查；
某个端点忘了接翻译，那一个端点就以 500 ``INTERNAL_ERROR``（可重试）作答，丢掉模型侧的原码。
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import replace
from typing import Any, TypeVar

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

import czghagent_ai.api.internal as internal
from czghagent_ai.app import app
from czghagent_ai.config import settings
from czghagent_ai.document_models import DocumentQaResult, DocumentRenderRequest
from czghagent_ai.errors import ServiceError
from czghagent_ai.services.ai_provider import (
    AiProviderAuthenticationError,
    AiProviderError,
    AiProviderNotConfiguredError,
    AiProviderOutputError,
    AiProviderTimeoutError,
    OpenAiCompatibleProvider,
)
from czghagent_ai.services.atlas_endpoints import AUTHORIZED_ENDPOINT_CODES, routed_endpoint_codes
from czghagent_ai.services.atlas_provider import (
    AtlasNotEntitledError,
    AtlasProvider,
    AtlasTaskIdMissingError,
    AtlasTokenRejectedError,
)
from czghagent_ai.services.document_qa import DocumentQaError
from czghagent_ai.services.file_readers import UnsupportedDocumentError
from czghagent_ai.tender_models import (
    BranchBlueprintRequest,
    ChapterDraftRequest,
    InterpretationRequest,
    OutlineAssemblyRequest,
    OutlineExpansionStageRequest,
    OutlineRequest,
    OutlineSkeletonStageRequest,
    ReviewRequest,
    RevisionRequest,
)


def _use_settings(monkeypatch: pytest.MonkeyPatch, **changes: Any) -> None:
    # 替换的是 internal 模块里那一份引用：出口选择、令牌校验、阶段时限都从那里读。
    monkeypatch.setattr(internal, "settings", replace(settings, **changes))


_Model = TypeVar("_Model", bound=BaseModel)


def _unchecked(model: type[_Model], **fields: Any) -> _Model:
    """不经校验的请求体。端点只把它原样交给服务；这里验的是失败翻译，不是请求校验。"""
    return model.model_construct(**fields)


# ── 模型出口 ───────────────────────────────────────────────────────────────


def test_atlas_is_chosen_whenever_it_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, atlas_api_url="http://atlas.local", deploy_stage="production")

    assert isinstance(internal.create_ai_provider(), AtlasProvider)
    exit_line = internal.describe_model_exit()
    assert "Atlas http://atlas.local" in exit_line
    # 只列真正会调用的路由：授权在手而没有调用点的那几条写进这一行，
    # 读日志的人会以为本产品在用 embedding / rerank。
    assert all(code in exit_line for code in routed_endpoint_codes())
    assert all(
        code not in exit_line for code in AUTHORIZED_ENDPOINT_CODES - set(routed_endpoint_codes())
    )


@pytest.mark.parametrize("stage", ["dev", "beta", "production"])
def test_a_deployed_stage_without_atlas_refuses_to_start(monkeypatch: pytest.MonkeyPatch, stage: str) -> None:
    """直连在部署态能跑、而且跑得很好——每次推理都不入平台的账，界面上没有任何症状。"""
    _use_settings(monkeypatch, atlas_api_url="", deploy_stage=stage, allow_mock_on_deploy=False)

    with pytest.raises(RuntimeError, match="ALLOW_MOCK_ON_DEPLOY"):
        internal.create_ai_provider()


def test_an_explicit_downgrade_on_deploy_is_allowed_and_says_so_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, atlas_api_url="", deploy_stage="beta", allow_mock_on_deploy=True)

    assert isinstance(internal.create_ai_provider(), OpenAiCompatibleProvider)
    exit_line = internal.describe_model_exit()
    assert exit_line.startswith("!!!")
    assert "beta" in exit_line


def test_local_development_connects_directly_without_the_alarm(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(
        monkeypatch, atlas_api_url="", deploy_stage="local", allow_mock_on_deploy=False,
        ai_model_base_url="http://model.local/v1",
    )

    assert isinstance(internal.create_ai_provider(), OpenAiCompatibleProvider)
    exit_line = internal.describe_model_exit()
    assert "直连 http://model.local/v1" in exit_line
    assert not exit_line.startswith("!!!")


# ── 失败翻译 ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exception", "status", "code", "retryable"),
    [
        # 运营侧漏了一条 endpoint 授权，和用户买没买无关：不是 403，也不是 NOT_ENTITLED。
        (AtlasNotEntitledError("未授权路由"), 503, "AI_ATLAS_NOT_ENTITLED", False),
        (AtlasTaskIdMissingError("缺少 task_id"), 500, "AI_TASK_ID_MISSING", False),
        (AiProviderNotConfiguredError("未配置"), 503, "AI_PROVIDER_NOT_CONFIGURED", False),
        (AiProviderAuthenticationError("凭据被拒"), 503, "AI_MODEL_AUTH_FAILED", True),
        (AiProviderTimeoutError("超时"), 504, "AI_MODEL_TIMEOUT", True),
        (AiProviderOutputError("输出不合法"), 502, "AI_OUTPUT_INVALID", False),
        # Java 侧重铸票后重试；这个服务原样再送必然再被拒，所以码必须原样带出。
        (AtlasTokenRejectedError("票被拒"), 502, "AI_ATLAS_TOKEN_REJECTED", True),
        (AiProviderError("上游失败"), 502, "AI_PROVIDER_ERROR", True),
    ],
    ids=lambda value: value.code if isinstance(value, AiProviderError) else None,
)
def test_each_model_failure_keeps_its_own_code_and_gets_the_right_status(
    exception: AiProviderError, status: int, code: str, retryable: bool
) -> None:
    error = internal.map_ai_error(exception)

    assert (error.status, error.code, error.retryable) == (status, code, retryable)
    assert error.message == str(exception)
    assert error.details["code"] == code


def test_a_stage_that_runs_past_its_deadline_is_a_timeout_naming_the_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, ai_model_stage_timeout_seconds=0.01)

    async def slow() -> None:
        await asyncio.sleep(5)

    with pytest.raises(AiProviderTimeoutError) as caught:
        asyncio.run(internal.run_ai_stage("chapter", slow))

    assert caught.value.stage == "chapter"
    assert caught.value.elapsed_millis is not None


def test_a_provider_failure_gets_the_stage_and_elapsed_time_attached() -> None:
    failure = AiProviderOutputError("输出不合法")

    async def failing() -> None:
        raise failure

    with pytest.raises(AiProviderOutputError) as caught:
        asyncio.run(internal.run_ai_stage("review", failing))

    assert caught.value is failure
    assert caught.value.stage == "review"
    assert caught.value.elapsed_millis is not None


def test_a_failure_that_already_knows_its_stage_keeps_it() -> None:
    """更靠近失败点的那一层知道得更准：外层只补空缺，不覆盖。"""

    async def failing() -> None:
        raise AiProviderError("上游失败", stage="atlas_chat", elapsed_millis=7)

    with pytest.raises(AiProviderError) as caught:
        asyncio.run(internal.run_ai_stage("outline_strategy", failing))

    assert (caught.value.stage, caught.value.elapsed_millis) == ("atlas_chat", 7)


# ── 每个模型端点都接上了翻译 ─────────────────────────────────────────────────


class _FailingService:
    """任何服务方法都以同一个模型侧失败结束。装配是同步方法，其余都是协程。"""

    def __init__(self, failure: AiProviderError) -> None:
        self._failure = failure

    def assemble_outline(self, _: object) -> None:
        raise self._failure

    def __getattr__(self, name: str) -> Callable[[object], Awaitable[None]]:
        async def fail(_: object) -> None:
            raise self._failure

        return fail


Endpoint = Callable[[Any], Coroutine[Any, Any, Any]]

_ENDPOINTS: list[tuple[str, Endpoint, object, str]] = [
    ("project-overview", internal.extract_project_overview, _unchecked(InterpretationRequest),
     "project_overview"),
    ("technical-scoring", internal.extract_technical_scoring, _unchecked(InterpretationRequest),
     "technical_scoring"),
    ("interpretation", internal.interpret_tender, _unchecked(InterpretationRequest), "interpretation"),
    ("outline", internal.plan_outline, _unchecked(OutlineRequest), "outline_legacy"),
    ("outline-strategy", internal.plan_outline_strategy, _unchecked(OutlineRequest), "outline_strategy"),
    ("outline-skeleton", internal.plan_outline_skeleton, _unchecked(OutlineSkeletonStageRequest),
     "outline_skeleton"),
    ("outline-expansion", internal.expand_outline_branch, _unchecked(OutlineExpansionStageRequest, batch_index=3),
     "outline_expansion_3"),
    ("chapter-blueprint", internal.plan_branch_blueprint, _unchecked(BranchBlueprintRequest),
     "branch_blueprint"),
    ("chapter", internal.draft_chapter, _unchecked(ChapterDraftRequest), "chapter"),
    ("revision", internal.revise_section, _unchecked(RevisionRequest), "revision"),
    ("review", internal.review_bid, _unchecked(ReviewRequest), "review"),
]


@pytest.mark.parametrize(("endpoint", "body", "stage"), [item[1:] for item in _ENDPOINTS],
                         ids=[item[0] for item in _ENDPOINTS])
def test_every_model_endpoint_translates_failures_and_names_its_stage(
    monkeypatch: pytest.MonkeyPatch, endpoint: Endpoint, body: object, stage: str
) -> None:
    monkeypatch.setattr(internal, "tender_ai_service", _FailingService(AiProviderTimeoutError("超时")))

    with pytest.raises(ServiceError) as caught:
        asyncio.run(endpoint(body))

    assert (caught.value.status, caught.value.code, caught.value.retryable) == (504, "AI_MODEL_TIMEOUT", True)
    assert caught.value.details["stage"] == stage


def test_assembly_failures_are_translated_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """装配不调模型、不走阶段计时，但合并失败同样是模型输出的问题，同样要带原码出去。"""
    monkeypatch.setattr(internal, "tender_ai_service", _FailingService(AiProviderOutputError("合并失败")))

    with pytest.raises(ServiceError) as caught:
        asyncio.run(internal.assemble_outline(_unchecked(OutlineAssemblyRequest)))

    assert (caught.value.status, caught.value.code, caught.value.retryable) == (502, "AI_OUTPUT_INVALID", False)


def test_a_model_failure_leaves_the_service_in_the_platform_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = AiProviderTimeoutError("AI model stage timed out")
    monkeypatch.setattr(internal, "tender_ai_service", _FailingService(failure))
    outline = {
        "requestId": "errors",
        "title": "失败路径技术标",
        "targetPages": 20,
        "biddingMode": "BLIND",
        "criteria": [{
            "id": "c1", "type": "PROJECT_OVERVIEW", "title": "概述",
            "description": "建设统一技术平台",
        }],
    }

    response = TestClient(app).post(
        "/internal/tender/outline/strategy",
        headers={"X-Internal-Token": settings.internal_token},
        json=outline,
    )

    assert response.status_code == 504
    body = response.json()
    assert {key: body[key] for key in ("code", "message", "retryable")} == {
        "code": "AI_MODEL_TIMEOUT", "message": "AI model stage timed out", "retryable": True,
    }
    # X-1 之外只多一个 details，给 Java 落诊断；不出现 FastAPI 的 {"detail": …}。
    assert set(body) == {"code", "message", "retryable", "details"}


# ── 解析与成稿 ─────────────────────────────────────────────────────────────


class _Raising:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    def parse(self, _: str, __: bytes) -> None:
        raise self._failure

    def render(self, _: DocumentRenderRequest) -> None:
        raise self._failure


def test_an_unsupported_upload_is_422_and_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一个文件再传一遍永远是同一个结果。"""
    monkeypatch.setattr(internal, "parser_service", _Raising(UnsupportedDocumentError("不支持的文件格式：.xyz")))

    response = TestClient(app).post(
        "/internal/parse",
        headers={"X-Internal-Token": settings.internal_token},
        files={"file": ("招标文件.xyz", b"\x00\x01", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "PARSER_DOCUMENT_UNSUPPORTED", "message": "不支持的文件格式：.xyz", "retryable": False,
    }


@pytest.mark.parametrize(
    ("failure", "status", "code", "retryable"),
    [
        # 载荷与目录对不上：换个时间重发还是对不上。
        (ValueError("章节与目录不一致"), 409, "DOCUMENT_RENDER_CONFLICT", False),
        # 渲染器或质量检查本身失败：可以再排一次。
        (DocumentQaError("LibreOffice 渲染失败"), 502, "DOCUMENT_RENDER_FAILED", True),
    ],
)
def test_render_failures_are_told_apart(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, status: int, code: str, retryable: bool
) -> None:
    monkeypatch.setattr(internal, "document_renderer", _Raising(failure))

    with pytest.raises(ServiceError) as caught:
        asyncio.run(internal.render_tender_document(_unchecked(DocumentRenderRequest)))

    assert (caught.value.status, caught.value.code, caught.value.retryable) == (status, code, retryable)
    assert caught.value.message == str(failure)


class _Renderer:
    def __init__(self, qa: DocumentQaResult) -> None:
        self._qa = qa

    def render(self, _: DocumentRenderRequest) -> tuple[bytes, DocumentQaResult]:
        return b"docx-bytes", self._qa


@pytest.mark.parametrize(("actual_pages", "header"), [(120, "120"), (None, "")])
def test_a_rendered_document_carries_its_quality_result_in_headers(
    monkeypatch: pytest.MonkeyPatch, actual_pages: int | None, header: str
) -> None:
    """摘要走 base64：中文放不进 HTTP 头，直接放会在代理那一跳被改写或拒绝。"""
    qa = DocumentQaResult(status="FAILED", actual_pages=actual_pages, summary="目标100页，实测120页，偏差+20页")
    monkeypatch.setattr(internal, "document_renderer", _Renderer(qa))

    response = asyncio.run(internal.render_tender_document(_unchecked(DocumentRenderRequest)))

    assert response.body == b"docx-bytes"
    assert response.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert response.headers["X-Actual-Pages"] == header
    assert response.headers["X-QA-Status"] == "FAILED"
    assert base64.urlsafe_b64decode(response.headers["X-QA-Summary-Base64"]).decode("utf-8") == qa.summary


# ── 系统验证：Atlas 探测端点 ───────────────────────────────────────────────


class _RecordingAtlas(AtlasProvider):
    def __init__(self) -> None:
        super().__init__("http://atlas.local")
        self.probed: list[str] = []

    async def probe(self, endpoint_code: str) -> dict[str, Any]:
        self.probed.append(endpoint_code)
        return {"endpointCode": endpoint_code, "ok": True}


def test_probe_defaults_to_the_routes_the_product_actually_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    atlas = _RecordingAtlas()
    monkeypatch.setattr(internal, "model_exit", atlas)

    asyncio.run(internal.probe_atlas(internal.AtlasProbeRequest()))

    assert atlas.probed == list(routed_endpoint_codes())


def test_probe_refuses_a_route_outside_the_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    """会花钱的端点不能变成「随便挑一个 code 打一次」的通道。"""
    atlas = _RecordingAtlas()
    monkeypatch.setattr(internal, "model_exit", atlas)

    with pytest.raises(ServiceError) as caught:
        asyncio.run(internal.probe_atlas(internal.AtlasProbeRequest(endpointCodes=["chat/fast", "chat/secret"])))

    assert (caught.value.status, caught.value.code) == (422, "AI_ATLAS_ENDPOINT_NOT_AUTHORIZED")
    assert atlas.probed == []


def test_probes_say_plainly_when_the_process_is_not_on_atlas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(internal, "model_exit", OpenAiCompatibleProvider("k", "http://x", "m", 30, 0))

    with pytest.raises(ServiceError) as caught:
        asyncio.run(internal.list_atlas_models())

    assert (caught.value.status, caught.value.code) == (503, "AI_ATLAS_NOT_CONFIGURED")


def test_a_model_failure_carries_its_diagnostics_in_the_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Java 把这些诊断落进 bid_ai_run_attempt。

    它们曾经只挂在异常对象上而从不序列化——每一次 AI 失败到了 Java 都只剩
    「AI 工作流执行失败」，2026-09-29 的请求体超限要读 Atlas 进程日志才定位出来。
    """
    failure = AiProviderTimeoutError("AI model stage timed out", stage="chapter_drafting", attempts=2)
    failure.atlas_code = "DEADLINE_EXCEEDED"  # type: ignore[attr-defined]
    monkeypatch.setattr(internal, "tender_ai_service", _FailingService(failure))

    response = TestClient(app).post(
        "/internal/tender/outline/strategy",
        headers={"X-Internal-Token": settings.internal_token},
        json={
            "requestId": "errors", "title": "失败路径技术标", "targetPages": 20, "biddingMode": "BLIND",
            "criteria": [{"id": "c1", "type": "PROJECT_OVERVIEW", "title": "概述", "description": "建设统一技术平台"}],
        },
    )

    body = response.json()
    assert body["code"] == "AI_MODEL_TIMEOUT"
    assert body["details"]["stage"] == "chapter_drafting"
    assert body["details"]["atlasCode"] == "DEADLINE_EXCEEDED"
    assert body["details"]["attempts"] == 2
