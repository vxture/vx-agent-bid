# GENERATED_BY_AI
# MODEL: claude-opus-5
# DATE: 2026-09-09
"""Atlas 客户端：发出去的是什么，收回来怎么读，什么时候该退避。

这一组盯的都是<b>不会报错的错法</b>：把产品码当 tenantId 送出去，
把上游没报用量的三个 0 当成真实消耗累加，把一个只有运营能解决的授权缺失
当成可重试的容量问题——三者都不抛异常，只会让账目或排查方向静默地错掉。
"""

from __future__ import annotations

import ast
import asyncio
import json
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

import czghagent_ai
from czghagent_ai.services.ai_provider import (
    AiProviderError,
    AiProviderNotConfiguredError,
    AiProviderOutputError,
    OpenAiCompatibleProvider,
    _operation_temperature,
)
from czghagent_ai.services.atlas_endpoints import (
    AUTHORIZED_ENDPOINT_CODES,
    DEFAULT_ENDPOINT_CODE,
    DETERMINISTIC_ENDPOINT_CODE,
    FAST_ENDPOINT_CODE,
    OPERATION_ROUTES,
    REASONING_ENDPOINT_CODE,
    endpoint_for,
    thinking_for,
)
from czghagent_ai.services.atlas_provider import (
    AtlasInputTooLargeError,
    AtlasNotEntitledError,
    AtlasOutputBudgetExhaustedError,
    AtlasProvider,
    AtlasTaskIdMissingError,
    AtlasTokenRejectedError,
)
from czghagent_ai.task_context import _s2s_token, _task_id, _tenant_id

TENANT_UUID = "11111111-2222-3333-4444-555555555555"


class _Answer(BaseModel):
    value: str


@pytest.fixture
def caller() -> Iterator[None]:
    """一个带齐 task_id / 票 / 租户的请求上下文。"""
    task = _task_id.set("task-1")
    token = _s2s_token.set("minted.jwt.value")
    tenant = _tenant_id.set(TENANT_UUID)
    yield
    _task_id.reset(task)
    _s2s_token.reset(token)
    _tenant_id.reset(tenant)


Handler = Callable[[httpx.Request], httpx.Response]


def _provider(
    handler: Handler, **kwargs: Any
) -> tuple[AtlasProvider, list[httpx.Request]]:
    """把一个假 Atlas 挂进传输层，于是断言看到的是真实发出去的字节。"""
    seen: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    provider = AtlasProvider(
        "http://atlas.internal",
        max_retries=1,
        transport=httpx.MockTransport(_record),
        **kwargs,
    )
    return provider, seen


def _run(provider: AtlasProvider, operation: str = "chapter_drafting") -> Any:
    return asyncio.run(provider.run(operation, {"a": 1}, "user-1", _Answer))


def _answers(body: dict[str, Any], status: int = 200) -> Handler:
    return lambda request: httpx.Response(status, json=body)


def _completion(content: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "atlas-req-1",
        "modelCode": "deepseek-v4-flash",
        "message": {"role": "assistant", "content": content},
        "usage": {"promptTokens": 120, "completionTokens": 40, "totalTokens": 160},
        "latencyMs": 900,
    }
    body.update(extra)
    return body


# ── endpoint 映射 ──────────────────────────────────────────────────────────


def _operations_the_service_calls() -> set[str]:
    """从源码里扫出每一处 ``execute_result("<operation>", ...)``。

    清单不手写：上一版手写着「八个」，而服务里真实发起调用的是十个，
    漏掉的两个静默落到兜底路由上，测试照样是绿的。
    """
    found: set[str] = set()
    for path in Path(czghagent_ai.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute_result"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value)
    return found


def test_every_operation_the_service_calls_has_a_route() -> None:
    """两个方向都查。

    漏登记一个：它静默落到 chat/default，那个环节用的是别人的生成参数——
    不报错，只让那一段产出变差。多登记一个：operation 已经被删掉而路由还在，
    下一个人无法从这张表判断哪些环节是活的。
    """
    assert set(OPERATION_ROUTES) == _operations_the_service_calls()


def test_routes_only_to_endpoints_that_are_authorized() -> None:
    """路由到未授权的 code，对应 operation 的每一次调用都是 403 NOT_ENTITLED。"""
    assert {route.endpoint_code for route in OPERATION_ROUTES.values()} <= (
        AUTHORIZED_ENDPOINT_CODES
    )


def _direct_era_route(operation: str) -> str:
    """按直连时代实测出来的策略，这个 operation 应该走哪条路由。

    直接问直连 provider 本身，而不是在这里再抄一遍它的策略表——
    抄出来的那一份，正是会和原件悄悄分叉的那一份。
    """
    provider = OpenAiCompatibleProvider(
        "sk-test", "https://api.deepseek.com", "fast-model", 30, 0,
        quality_model="quality-model",
    )
    request: dict[str, Any] = {}
    provider._apply_thinking_policy(request, operation, {})
    if request.get("thinking") == {"type": "enabled"}:
        return REASONING_ENDPOINT_CODE
    if _operation_temperature(operation) == 0:
        return DETERMINISTIC_ENDPOINT_CODE
    if provider._model_for(operation) == "quality-model":
        return DEFAULT_ENDPOINT_CODE
    return FAST_ENDPOINT_CODE


@pytest.mark.parametrize("operation", sorted(OPERATION_ROUTES))
def test_routes_follow_the_strategy_measured_in_the_direct_era(operation: str) -> None:
    """分档依据是实测过的 thinking / 温度 / 模型档位，不是按路由名字猜。

    最该守住的是两对：一致性审查（开 thinking）与正文续写（温度 0.4）不能落在
    同一条路由上；局部改写是 Quality 模型却刻意关 thinking，不能因为「要质量」
    就被推到 reasoning——那会让推理吃掉替换正文的补全预算。
    """
    assert endpoint_for(operation) == _direct_era_route(operation)


def test_unknown_operation_routes_somewhere_rather_than_failing() -> None:
    assert endpoint_for("a_new_operation") == DEFAULT_ENDPOINT_CODE


# ── 请求形状 ───────────────────────────────────────────────────────────────


def test_sends_the_fields_atlas_actually_reads(caller: None) -> None:
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider)

    body = json.loads(seen[0].content)
    assert body["taskId"] == "task-1"
    assert body["requestId"], "requestId 在客户端生成——它是 Atlas 请求日志里唯一的定位手段"
    assert len(body["messages"]) == 2
    assert seen[0].headers["authorization"] == "Bearer minted.jwt.value"


@pytest.mark.parametrize(
    ("operation", "endpoint_code"),
    [
        ("technical_scoring_extraction", DETERMINISTIC_ENDPOINT_CODE),
        ("chapter_drafting", FAST_ENDPOINT_CODE),
        ("section_revision", DEFAULT_ENDPOINT_CODE),
        ("consistency_review", REASONING_ENDPOINT_CODE),
    ],
)
def test_puts_the_routed_endpoint_on_the_wire(
    caller: None, operation: str, endpoint_code: str
) -> None:
    """映射表对了不等于发出去的对了——看的是传输层上真实的字节。

    四条路由各取一个 operation：客户端若忽略映射、一律发 chat/default，
    这里至少三条会红。
    """
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider, operation)

    assert json.loads(seen[0].content)["endpointCode"] == endpoint_code


def test_sends_the_tenant_uuid_from_the_token_not_the_product_code(
    caller: None,
) -> None:
    """tenantId 取自票里的 claim。

    送产品码看起来能跑：Atlas 只校验它非空，而产品授权那条路径在租户断言之前
    就返回了。一旦授权缺失或 endpoint 被改指，控制流落到 UUID 断言上，
    失败表现为 400 INVALID_TENANT_ID——读起来像请求体写错了。非 UUID 还会让
    Atlas 的请求日志写进 NULL，本产品的流量就从每一张租户汇总表里消失。
    """
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider)

    body = json.loads(seen[0].content)
    assert body["tenantId"] == TENANT_UUID
    assert body["tenantId"] != "tenderforge"


def test_refuses_to_call_without_a_task_id() -> None:
    """Atlas 从 v0.15.0 起强制要求 taskId，缺失即 400。

    在这里提前拒绝，是因为 Atlas 的报错落在网络那一端，而这里能说清楚断的是
    哪一段——task_id 由 Java 入站带入，缺失说明中间某一跳把它丢了。
    """
    token = _s2s_token.set("t")
    try:
        provider, seen = _provider(_answers(_completion('{"value":"ok"}')))
        with pytest.raises(AtlasTaskIdMissingError):
            _run(provider)
        assert not seen, "没有 task_id 就不该把请求送出去"
    finally:
        _s2s_token.reset(token)


def test_refuses_to_call_without_a_minted_token() -> None:
    """票由 Java 侧现铸并转呈；没带票就明确拒绝，不要送出去让 Atlas 回 401。

    401 看起来像凭据配错了，而真相是根本没带——两者要查的地方完全不同。
    """
    task = _task_id.set("task-1")
    try:
        provider, seen = _provider(_answers(_completion('{"value":"ok"}')))
        with pytest.raises(AiProviderNotConfiguredError):
            _run(provider)
        assert not seen
    finally:
        _task_id.reset(task)


def test_refuses_when_atlas_is_not_configured() -> None:
    with pytest.raises(AiProviderNotConfiguredError):
        asyncio.run(AtlasProvider("").run("chapter_drafting", {}, "u", _Answer))


# ── 回答的读法 ─────────────────────────────────────────────────────────────


def test_decodes_structured_output_and_usage(caller: None) -> None:
    provider, _ = _provider(_answers(_completion('{"value":"ok"}')))

    result = _run(provider)

    assert result.data == {"value": "ok"}
    assert result.diagnostics.input_tokens == 120
    assert result.diagnostics.output_tokens == 40


def test_reports_no_usage_rather_than_zero_when_upstream_reported_none(
    caller: None,
) -> None:
    """上游没报用量时 Atlas 返回三个 0，而它自己内部记的是 NULL。

    把这些 0 当成真实消耗累加会让消耗被低估，且看起来一切正常——
    「这次没花 token」和「花了多少没人知道」是两件不同的事。
    """
    body = _completion('{"value":"ok"}')
    body["usage"] = {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}
    provider, _ = _provider(_answers(body))

    result = _run(provider)

    assert result.diagnostics.input_tokens is None
    assert result.diagnostics.output_tokens is None


def test_extracts_json_from_a_fenced_answer(caller: None) -> None:
    """Atlas 的请求体里没有 response_format，模型可能加代码围栏。

    直连时这件事由 ``response_format=json_object`` 挡掉；迁到 Atlas 之后，
    产品原有的宽容解码器就是<b>唯一</b>的那道防线。
    """
    provider, _ = _provider(_answers(_completion('```json\n{"value":"ok"}\n```')))

    assert _run(provider).data == {"value": "ok"}


def test_reports_truncation_as_such(caller: None) -> None:
    provider, _ = _provider(
        _answers(_completion('{"value":"o', finishReason="length"))
    )

    with pytest.raises(AiProviderOutputError) as failure:
        _run(provider)

    assert "截断" in str(failure.value)


# ── 错误与重试 ─────────────────────────────────────────────────────────────


def test_surfaces_a_rejected_token_without_retrying_it(caller: None) -> None:
    """这个服务不铸票，原样再送一遍同一张必然再被拒。

    重铸由 Java 侧完成——在这里退避重试是纯粹的浪费，而且会把一次凭据问题的
    等待时间乘以重试次数。
    """
    provider, seen = _provider(
        _answers({"code": "S2S_TOKEN_INVALID", "message": "expired"}, status=401)
    )

    with pytest.raises(AtlasTokenRejectedError):
        _run(provider)

    assert len(seen) == 1, "拒票不重试"


def test_names_a_missing_grant_as_such_and_never_retries_it(caller: None) -> None:
    """授权缺失是运营侧的一次动作，退避多久都不会自己变好。

    而且它<b>不是</b>通则那个 NOT_ENTITLED 的含义——那个码说的是「这个用户没买」，
    会被渲染成一句「请先订阅」，把所有人朝错误的方向带。
    """
    provider, seen = _provider(
        _answers({"code": "NOT_ENTITLED", "message": "no grant"}, status=403)
    )

    with pytest.raises(AtlasNotEntitledError) as failure:
        _run(provider)

    assert len(seen) == 1
    assert failure.value.code == "AI_ATLAS_NOT_ENTITLED"
    assert "授权" in str(failure.value)


def test_does_not_retry_a_commercial_ceiling_that_arrives_as_429(caller: None) -> None:
    """QUOTA_EXCEEDED 以 429 到达，长得和会自己恢复的容量闸门一模一样。

    按状态码判会一路重试到耗尽——而只有运营抬高上限才可能成功。
    """
    provider, seen = _provider(
        _answers({"code": "QUOTA_EXCEEDED", "message": "pool exhausted"}, status=429)
    )

    with pytest.raises(AiProviderError):
        _run(provider)

    assert len(seen) == 1, "商业上限不重试"


def test_does_not_retry_a_capability_gap_that_arrives_as_501(caller: None) -> None:
    """MODEL_NOT_IMPLEMENTED 是 501，落在 5xx 里却绝不该重试——
    上游根本没有这个能力，重试只是把超时再付一遍。
    """
    provider, seen = _provider(
        _answers({"code": "MODEL_NOT_IMPLEMENTED", "message": "nope"}, status=501)
    )

    with pytest.raises(AiProviderError):
        _run(provider)

    assert len(seen) == 1


def test_retries_a_transient_upstream_failure(caller: None) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                503, json={"code": "PROVIDER_UNAVAILABLE", "message": "down"}
            )
        return httpx.Response(200, json=_completion('{"value":"ok"}'))

    provider, seen = _provider(handler)

    assert _run(provider).data == {"value": "ok"}
    assert len(seen) == 2


def test_lets_the_callee_override_the_local_retry_table(caller: None) -> None:
    """被调方自己说了不能重试，就不重试——即使本地码表没见过这个码。

    反过来让本地硬编的表说了算，等于 Atlas 每加一个新错误码，
    我们就按猜的方式处理它一次。
    """
    provider, seen = _provider(
        _answers(
            {"code": "A_BRAND_NEW_CODE", "message": "x", "retryable": False},
            status=503,
        )
    )

    with pytest.raises(AiProviderError):
        _run(provider)

    assert len(seen) == 1


def test_survives_an_error_body_that_is_not_json(caller: None) -> None:
    """代理页面、被截断的响应——不能因为读不懂错误体就抛一个解析异常。"""
    provider, _ = _provider(
        lambda request: httpx.Response(502, text="<html>bad gateway</html>")
    )

    with pytest.raises(AiProviderError) as failure:
        _run(provider)

    assert "UNKNOWN" in str(failure.value)


# ── 归因字段与系统验证探测 ─────────────────────────────────────────────────


def test_every_call_says_which_operation_spent_it(caller: None) -> None:
    """featureId 是 Atlas 里把一份标书的推理消耗拆到环节上的唯一维度。

    applicationType 与 applicationId 必须成对：只送前者，Atlas 对每一次调用答
    400 APPLICATION_ID_REQUIRED——v0.1.20 就这样让生产上全部模型调用中断。
    applicationId 又必须是 UUID（Atlas 授权查询按 UUID 转型）。
    """
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider, "consistency_review")
    _run(provider, "chapter_drafting")

    first, second = (json.loads(request.content) for request in seen)
    assert first["applicationType"] == "agent"
    assert first["featureId"] == "consistency_review"
    assert "applicationId" in first, "送了 applicationType 就必须送 applicationId"
    assert str(uuid.UUID(first["applicationId"])) == first["applicationId"]
    # 同一个任务的调用归到同一个 application 下。
    assert second["applicationId"] == first["applicationId"]


def test_application_id_follows_the_task(caller: None) -> None:
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider)
    other = _task_id.set("task-2")
    try:
        _run(provider)
    finally:
        _task_id.reset(other)

    ids = [json.loads(request.content)["applicationId"] for request in seen]
    assert ids[0] != ids[1]


def test_probe_carries_the_same_attribution_triple(caller: None) -> None:
    provider, seen = _provider(_answers(_completion("pong")))

    asyncio.run(provider.probe(FAST_ENDPOINT_CODE))

    body = json.loads(seen[0].content)
    assert {"applicationType", "applicationId", "featureId"} <= set(body)


@pytest.mark.parametrize(
    "answer",
    [
        [{"modelCode": "m-1"}, {"modelCode": "m-2"}],
        {"data": [{"id": "m-1"}, {"code": "m-2"}]},
        {"models": ["m-1", "m-2"]},
    ],
)
def test_model_list_is_read_with_the_same_ticket(caller: None, answer: Any) -> None:
    provider, seen = _provider(_answers(answer))

    codes = asyncio.run(provider.list_models())

    assert codes == ["m-1", "m-2"]
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/v1/models"
    assert seen[0].headers["authorization"] == "Bearer minted.jwt.value"


def test_model_list_refusal_carries_atlas_code(caller: None) -> None:
    provider, _ = _provider(_answers({"code": "S2S_TOKEN_INVALID", "message": "bad"}, 401))

    with pytest.raises(AtlasTokenRejectedError):
        asyncio.run(provider.list_models())


def _probe_answer(thinking: object = "off", reasoning: str | None = None) -> dict[str, Any]:
    answer = _completion("pong", thinking=thinking)
    if reasoning is not None:
        answer["message"]["reasoning"] = reasoning
    return answer


def test_probe_is_one_capped_call_on_the_named_route(caller: None) -> None:
    provider, seen = _provider(_answers(_probe_answer()))

    result = asyncio.run(provider.probe(REASONING_ENDPOINT_CODE))

    body = json.loads(seen[0].content)
    assert body["endpointCode"] == REASONING_ENDPOINT_CODE
    assert body["maxTokens"] == 8, "探测要证明的是链路活着，补全上限压到最小"
    assert body["thinking"] == "off", "8 个 token 在默认开推理的模型上会全部花在推理上"
    assert body["temperature"] == 0
    assert body["taskId"] == "task-1"
    assert body["tenantId"] == TENANT_UUID
    assert body["featureId"] == "diagnostics.atlas_probe"
    assert result == {
        "endpointCode": REASONING_ENDPOINT_CODE,
        "ok": True,
        "modelCode": "deepseek-v4-flash",
        "latencyMs": 900,
        "totalTokens": 160,
        "thinking": "off",
        "reasoningReturned": False,
    }


@pytest.mark.parametrize(
    ("echoed", "reasoning"),
    [(None, None), ("on", None), ("off", "先想一想……")],
    ids=["no-echo", "echo-on", "off-but-reasoned"],
)
def test_probe_fails_a_route_that_did_not_honour_thinking_off(
    caller: None, echoed: object, reasoning: str | None
) -> None:
    """回显不是 off、或带 off 仍返回推理内容：解读类环节的推理成本还在，这条路由不算通过。"""
    provider, _ = _provider(_answers(_probe_answer(echoed, reasoning)))

    result = asyncio.run(provider.probe(DETERMINISTIC_ENDPOINT_CODE))

    assert result["ok"] is False
    assert result["code"] == "AI_THINKING_NOT_HONOURED"


def test_probe_reports_a_refused_route_instead_of_raising(caller: None) -> None:
    """一条路由未授权不能遮住其余几条：失败写进结果，不抛出。"""
    provider, _ = _provider(_answers({"code": "NOT_ENTITLED", "message": "no grant"}, 403))

    result = asyncio.run(provider.probe(FAST_ENDPOINT_CODE))

    assert result["ok"] is False
    assert result["code"] == "AI_ATLAS_NOT_ENTITLED"
    assert "no grant" in result["message"]


def test_probe_without_a_ticket_makes_no_call() -> None:
    provider, seen = _provider(_answers(_completion("pong")))
    task = _task_id.set("task-1")
    try:
        result = asyncio.run(provider.probe(FAST_ENDPOINT_CODE))
    finally:
        _task_id.reset(task)

    assert result["ok"] is False
    assert seen == []


# ── 生成参数（Atlas v0.7.8 起按调用传，#69） ─────────────────────────────


@pytest.mark.parametrize("operation", sorted(OPERATION_ROUTES))
def test_every_call_carries_the_generation_parameters_measured_in_the_direct_era(
    caller: None, operation: str
) -> None:
    """不带 thinking 就是上游默认，而默认通常是开推理：解读环节因此 78% 的输出是推理。"""
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider, operation)

    body = json.loads(seen[0].content)
    expected_thinking = "on" if endpoint_for(operation) == REASONING_ENDPOINT_CODE else "off"
    assert body["thinking"] == expected_thinking
    assert body["temperature"] == _operation_temperature(operation)


def test_reasoning_is_on_exactly_for_the_three_operations_that_need_it() -> None:
    on = {operation for operation in OPERATION_ROUTES if thinking_for(operation) == "on"}
    assert on == {"bid_strategy_planning", "branch_blueprint_planning", "consistency_review"}


def test_deterministic_extraction_runs_cold_and_without_reasoning(caller: None) -> None:
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider, "project_overview_source_selection")

    body = json.loads(seen[0].content)
    assert (body["thinking"], body["temperature"], body["maxTokens"]) == ("off", 0, 4096)


def test_atlas_enforces_a_deadline_shorter_than_our_own(caller: None) -> None:
    """我们先放弃而 Atlas 还在生成，这一截是白付的钱：总时限交给 Atlas，并且比本地读超时短。"""
    handler = _answers(_completion('{"value":"ok"}'))
    seen: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    provider = AtlasProvider(
        "http://atlas.internal", timeout_seconds=90, transport=httpx.MockTransport(_record)
    )
    _run(provider)

    assert json.loads(seen[0].content)["timeoutMs"] == 88_000


@pytest.mark.parametrize(
    "code", ["PAYLOAD_TOO_LARGE", "CONTEXT_LENGTH_EXCEEDED", "UPSTREAM_REJECTED_REQUEST"]
)
def test_input_too_large_is_one_code_and_is_not_retried(caller: None, code: str) -> None:
    provider, seen = _provider(_answers({"code": code, "message": "too big", "retryable": False}, 422))

    with pytest.raises(AtlasInputTooLargeError) as caught:
        _run(provider)

    assert len(seen) == 1, "同一个请求重发多少次都一样大"
    assert caught.value.details()["atlasCode"] == code


def test_output_budget_spent_on_reasoning_is_named_and_not_retried(caller: None) -> None:
    provider, seen = _provider(
        _answers({"code": "OUTPUT_BUDGET_EXHAUSTED", "message": "all reasoning", "retryable": False}, 422)
    )

    with pytest.raises(AtlasOutputBudgetExhaustedError):
        _run(provider)

    assert len(seen) == 1


def test_an_atlas_deadline_is_a_timeout_that_is_not_retried_locally(caller: None) -> None:
    provider, seen = _provider(
        _answers({"code": "DEADLINE_EXCEEDED", "message": "late", "retryable": False}, 504)
    )

    with pytest.raises(AiProviderError) as caught:
        _run(provider)

    assert caught.value.code == "AI_MODEL_TIMEOUT"
    assert len(seen) == 1


# ── 路由容量核对（GET /v1/model-routes，Atlas v0.7.7 起） ────────────────


def _routes(**overrides: dict[str, Any]) -> dict[str, Any]:
    base = {
        code: {
            "endpointCode": code, "category": "chat", "state": "active",
            "contextWindow": 256000, "maxOutputTokens": 128000, "thinkingModes": ["off", "on"],
        }
        for code in ("chat/default", "chat/deterministic", "chat/fast", "chat/reasoning", "chat/vision")
    }
    for code, change in overrides.items():
        base[code.replace("_", "/")].update(change)
    return {"endpoints": list(base.values()), "maxRequestBytes": 16_777_216}


def test_route_capacity_is_read_with_the_same_ticket_and_checks_only_our_routes(caller: None) -> None:
    provider, seen = _provider(_answers(_routes()))

    result = asyncio.run(provider.route_capacity())

    assert seen[0].url.path == "/v1/model-routes"
    assert seen[0].headers["authorization"] == "Bearer minted.jwt.value"
    assert result["maxRequestBytes"] == 16_777_216
    assert [route["endpointCode"] for route in result["routes"]] == [
        "chat/default", "chat/deterministic", "chat/fast", "chat/reasoning",
    ], "只核对本产品实际路由的四条，不包括授权在手而未使用的 chat/vision"
    assert all(route["ok"] for route in result["routes"])
    reasoning = next(route for route in result["routes"] if route["endpointCode"] == "chat/reasoning")
    assert reasoning["requiredThinking"] == ["on"]
    deterministic = next(route for route in result["routes"] if route["endpointCode"] == "chat/deterministic")
    assert deterministic["requiredThinking"] == ["off"]


def test_a_route_that_cannot_turn_reasoning_off_fails_the_check(caller: None) -> None:
    """运营改指向到只支持 on 的模型：这条路由上的每一次调用都会 422 THINKING_MODE_UNSUPPORTED。"""
    provider, _ = _provider(_answers(_routes(chat_deterministic={"thinkingModes": ["on"]})))

    result = asyncio.run(provider.route_capacity())

    route = next(item for item in result["routes"] if item["endpointCode"] == "chat/deterministic")
    assert route["ok"] is False
    assert "off" in route["problems"][0]


def test_a_window_too_small_for_our_largest_input_fails_the_check(caller: None) -> None:
    provider, _ = _provider(_answers(_routes(chat_fast={"contextWindow": 32_000})))

    result = asyncio.run(provider.route_capacity())

    route = next(item for item in result["routes"] if item["endpointCode"] == "chat/fast")
    assert route["ok"] is False
    assert "32000" in route["problems"][0]


def test_unknown_capacity_is_reported_as_unknown_not_as_passing(caller: None) -> None:
    provider, _ = _provider(_answers(_routes(chat_default={"contextWindow": None, "thinkingModes": None})))

    result = asyncio.run(provider.route_capacity())

    route = next(item for item in result["routes"] if item["endpointCode"] == "chat/default")
    assert route["unknown"] == ["thinkingModes", "contextWindow"]


def test_a_route_missing_from_the_list_fails(caller: None) -> None:
    body = _routes()
    body["endpoints"] = [item for item in body["endpoints"] if item["endpointCode"] != "chat/fast"]
    provider, _ = _provider(_answers(body))

    result = asyncio.run(provider.route_capacity())

    route = next(item for item in result["routes"] if item["endpointCode"] == "chat/fast")
    assert route["ok"] is False


# ── 流式调用（上游非流式时要生成完才回头，Atlas 等响应头只给 30 秒） ──────────


def _sse(*frames: object) -> Handler:
    body = "".join(
        f"data: {frame if isinstance(frame, str) else json.dumps(frame, ensure_ascii=False)}\n\n"
        for frame in frames
    )
    return lambda request: httpx.Response(
        200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"}
    )


def test_business_calls_ask_atlas_to_stream(caller: None) -> None:
    provider, seen = _provider(_answers(_completion('{"value":"ok"}')))

    _run(provider)

    assert json.loads(seen[0].content)["stream"] is True
    assert "text/event-stream" in seen[0].headers["accept"]


def test_text_frames_are_assembled_into_the_answer(caller: None) -> None:
    provider, _ = _provider(_sse(
        {"type": "text", "delta": '{"val'},
        {"type": "text", "delta": 'ue":"流式"}'},
        {"type": "done", "finishReason": "stop",
         "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}},
        "[DONE]",
    ))

    result = _run(provider)

    assert result.data == {"value": "流式"}
    assert result.diagnostics.output_tokens == 5


def test_a_mid_stream_error_is_translated_like_an_http_error(caller: None) -> None:
    provider, seen = _provider(_sse(
        {"type": "text", "delta": '{"va'},
        {"type": "error", "code": "CONTEXT_LENGTH_EXCEEDED", "message": "too long", "retryable": False},
    ))

    with pytest.raises(AtlasInputTooLargeError):
        _run(provider)

    assert len(seen) == 1, "不可重试的中途失败不重发"


def test_a_stream_that_ends_before_done_is_not_taken_as_a_complete_answer(caller: None) -> None:
    """半截答案当完整答案用是最坏的结局：没有 done 帧就按不完整处理（可重试一次）。"""
    provider, seen = _provider(_sse({"type": "text", "delta": '{"value":"半截'}))

    with pytest.raises(AiProviderError) as caught:
        _run(provider)

    assert "STREAM_INCOMPLETE" in str(caught.value)
    assert len(seen) == 2, "不完整的流重试一次"


def test_an_unparseable_upstream_frame_does_not_discard_a_good_answer(caller: None) -> None:
    provider, _ = _provider(_sse(
        {"type": "text", "delta": '{"value":'},
        {"type": "error", "code": "UPSTREAM_FRAME_UNPARSEABLE", "message": "one bad frame"},
        {"type": "text", "delta": '"ok"}'},
        {"type": "done", "finishReason": "stop", "usage": {}},
    ))

    assert _run(provider).data == {"value": "ok"}


# ── 对齐 Atlas v0.7.18：用量子集、实际模型、限流等待、契约指纹 ──────────────


def test_reasoning_and_cached_tokens_and_the_answering_model_are_recorded(caller: None) -> None:
    """Atlas 口径：reasoningTokens ⊂ completionTokens，cachedInputTokens ⊂ promptTokens。"""
    answer = _completion('{"value":"ok"}', modelCode="doubao-seed-2-0-lite-260428")
    answer["usage"].update({"reasoningTokens": 12, "cachedInputTokens": 30})
    provider, _ = _provider(_answers(answer))

    diagnostics = _run(provider).diagnostics

    assert (diagnostics.reasoning_tokens, diagnostics.cached_input_tokens) == (12, 30)
    assert diagnostics.model_code == "doubao-seed-2-0-lite-260428"


def test_a_subset_atlas_did_not_report_stays_unknown_not_zero(caller: None) -> None:
    provider, _ = _provider(_answers(_completion('{"value":"ok"}')))

    diagnostics = _run(provider).diagnostics

    assert diagnostics.reasoning_tokens is None
    assert diagnostics.cached_input_tokens is None


def test_the_streamed_done_frame_reports_the_model_that_actually_answered(caller: None) -> None:
    provider, _ = _provider(_sse(
        {"type": "text", "delta": '{"value":"ok"}'},
        {"type": "done", "finishReason": "stop", "modelCode": "deepseek-v4-flash",
         "usage": {"promptTokens": 3, "completionTokens": 2, "totalTokens": 5}},
    ))

    assert _run(provider).diagnostics.model_code == "deepseek-v4-flash"


def test_rate_limiting_waits_as_long_as_atlas_asks(caller: None, monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []

    async def record_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("czghagent_ai.services.atlas_provider.asyncio.sleep", record_sleep)
    responses = iter([
        httpx.Response(429, json={"code": "RATE_LIMITED", "message": "slow down",
                                  "retryable": True, "retryAfterMs": 4500}),
        httpx.Response(200, json=_completion('{"value":"ok"}')),
    ])
    provider, _ = _provider(lambda request: next(responses))

    _run(provider)

    assert waits == [4.5]


def test_the_contract_fingerprint_is_compared_with_the_one_this_client_was_checked_against(
    caller: None,
) -> None:
    from czghagent_ai.services.atlas_provider import ATLAS_CONTRACT_FINGERPRINT

    same, _ = _provider(_answers({"fingerprint": ATLAS_CONTRACT_FINGERPRINT, "errorCodes": [{}] * 52}))
    moved, seen = _provider(_answers({"fingerprint": "c1-000000000000", "errorCodes": []}))

    assert asyncio.run(same.contract())["matches"] is True
    result = asyncio.run(moved.contract())
    assert result["matches"] is False
    assert result["pinned"] == ATLAS_CONTRACT_FINGERPRINT
    assert seen[0].url.path == "/.well-known/vxture-contract"
    assert seen[0].headers["authorization"] == "Bearer minted.jwt.value"
