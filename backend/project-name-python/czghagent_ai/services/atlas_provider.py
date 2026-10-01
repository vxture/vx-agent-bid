# GENERATED_BY_AI
# MODEL: claude-opus-5
# DATE: 2026-09-09
"""Atlas 模型供给面客户端——本产品<b>唯一</b>的模型出口。

通则把 Atlas 定为唯一模型出口和唯一推理计量入口。「唯一」这两个字是整件事的
全部意义：只要还有一条直连的旁路，平台侧的推理账目就永远是残缺的，
而残缺的表现不是报错，是月底对不上而没有人说得清差在哪。

**令牌不在这个进程里铸。** Atlas 要的是 ``aud=atlas`` 的 S2S 票，而铸票凭据
就是本产品的 OIDC client 对。把那对凭据复制进 Python 服务意味着产品身份
凭据有了第二份副本、两个轮换点。所以 Java 侧每次调用现铸并随请求头带过来，
这个服务只负责转呈。票只活 300 秒，也确实没有别的用法。

**这里不上报 token 用量。** Atlas 自己按 ``atlas.chat`` 计量推理消耗，
产品再报一次就是同一次推理被记两遍。产品该报的是自己的业务单元（C3 上行），
那些东西 Atlas 看不见。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from czghagent_ai.services.ai_provider import (
    AiProviderAuthenticationError,
    AiProviderDiagnostics,
    AiProviderError,
    AiProviderNotConfiguredError,
    AiProviderOutputError,
    AiProviderResult,
    AiProviderTimeoutError,
    _decode_json_object,
    _elapsed_millis,
    _operation_max_tokens,
    _operation_prompt,
    _operation_temperature,
    _text_hash,
)
from czghagent_ai.services.atlas_endpoints import (
    REQUIRED_CONTEXT_TOKENS,
    endpoint_for,
    route_requirements,
    thinking_for,
)
from czghagent_ai.task_context import current_atlas_identity, current_task_id

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class AtlasNotEntitledError(AiProviderError):
    """本产品没有被授权路由到这个 endpoint。

    与「令牌无效」是两件事，而且是<b>唯一</b>一种重试永远无用的失败：
    授权是运营侧的一次动作，退避多久都不会自己变好。
    """

    code = "AI_ATLAS_NOT_ENTITLED"


class AtlasTokenRejectedError(AiProviderError):
    """Atlas 拒绝了这张票。

    这个服务不铸票，所以只能把它原样报给 Java——由铸币的那一侧作废缓存、
    重铸、再来一次。在这里退避重试是纯粹的浪费：同一张被拒的票再送一遍
    仍然会被拒。
    """

    code = "AI_ATLAS_TOKEN_REJECTED"


class AtlasTaskIdMissingError(AiProviderError):
    """没有 task_id。

    Atlas 从 v0.15.0 起强制要求它（缺失即 400）。本服务提前拒绝而不是把请求
    送出去，是因为 Atlas 的报错落在网络那一端，而这里能说清楚缺的是哪一段
    ——task_id 由 Java 入站带入，断在这里说明中间某一跳把它丢了。
    """

    code = "AI_TASK_ID_MISSING"


#: 哪些 Atlas 错误码值得退避重试。
#:
#: 用状态码范围表达不了这张表：``MODEL_NOT_IMPLEMENTED`` 是 501 却<b>绝不</b>该重试
#: ——上游根本没有这个能力，重试只是把超时再付一遍；``QUOTA_EXCEEDED`` 可能以 429
#: 到达，同样不该重试——一个只有运营能抬高的商业上限，长得和会自己恢复的容量闸门
#: 一模一样，只有错误码能把它们分开。
_RETRYABLE_CODES: dict[str, bool] = {
    "RATE_LIMITED": True,
    "PROVIDER_UNAVAILABLE": True,
    "MODEL_RUNTIME_STREAM_FAILED": True,
    "UPSTREAM_FRAME_UNPARSEABLE": True,
    "MODEL_NOT_IMPLEMENTED": False,
    "MODEL_NOT_ROUTABLE": False,
    "ENDPOINT_NOT_ROUTABLE": False,
    "TASK_PROFILE_NOT_ROUTABLE": False,
    "NOT_ENTITLED": False,
    "QUOTA_EXCEEDED": False,
    "INVALID_TENANT_ID": False,
    "INVALID_APPLICATION_ID": False,
    "CANDIDATE_POOL_TOO_LARGE": False,
    # Atlas v0.7.6–v0.7.10（#69）新增。全部不可重试：同一个请求重发多少次都一样大、
    # 一样超时、一样把输出预算花在推理上。
    "PAYLOAD_TOO_LARGE": False,
    "REQUEST_BODY_MALFORMED": False,
    "CONTEXT_LENGTH_EXCEEDED": False,
    "UPSTREAM_REJECTED_REQUEST": False,
    "OUTPUT_BUDGET_EXHAUSTED": False,
    "THINKING_MODE_UNSUPPORTED": False,
    "CHAT_THINKING_INVALID": False,
    "CHAT_TIMEOUT_INVALID": False,
    "DEADLINE_EXCEEDED": False,
}

#: 本产品按其核对过的 Atlas 契约指纹（v0.7.18，2026-10-01）。
#:
#: 指纹只在必填规则或错误码词表变化时才动。系统验证每次都拉一次线上值来比：不一致就是
#: Atlas 改了契约，要对着新的 ``requests`` / ``errorCodes`` 逐条核对本客户端，再改这里。
#: 不靠对方记得通知——Atlas 侧自己也说过漏报过一次指纹移动。
ATLAS_CONTRACT_FINGERPRINT = "c1-5f484ea774f6"

#: 「输入太大，需要分片」的三种说法（Atlas #69）。上游识别出来的超窗口是
#: CONTEXT_LENGTH_EXCEEDED，识别不出的是 UPSTREAM_REJECTED_REQUEST，网关入口的是
#: PAYLOAD_TOO_LARGE——对产品而言处置相同，所以收成一个码。
_INPUT_TOO_LARGE_CODES = frozenset(
    {"PAYLOAD_TOO_LARGE", "CONTEXT_LENGTH_EXCEEDED", "UPSTREAM_REJECTED_REQUEST"}
)


class AtlasInputTooLargeError(AiProviderError):
    """输入超出了网关请求体上限或所路由模型的上下文窗口。不可重试，要分片。"""

    code = "AI_INPUT_TOO_LARGE"


class AtlasOutputBudgetExhaustedError(AiProviderError):
    """输出预算在产出正文之前就被推理用完了。不可重试：同样的预算会同样用完。"""

    code = "AI_OUTPUT_BUDGET_EXHAUSTED"

#: 单次调用的预算，与直连同一档（``AI_MODEL_TIMEOUT_SECONDS``，详细设计 §8.2 的
#: 240 / 540 / 600 / 720 链的第一环）。
#:
#: 这里曾经是单独的 ``ATLAS_TIMEOUT_SECONDS=90``，只按解读类的短调用定。v0.1.22 起它还
#: 决定交给 Atlas 的 ``timeoutMs``，于是开推理的目录策略在 88 秒被 Atlas 按时限取消
#: （2026-09-30，DEADLINE_EXCEEDED）——推理路由上的调用合法地需要数分钟。
_DEFAULT_TIMEOUT_SECONDS = 240.0


class AtlasProvider:
    """把一次 operation 变成一次 Atlas ``/v1/chat`` 调用。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=30.0)
        # 交给 Atlas 的整次调用总时限，比我们自己的读超时短一点。
        #
        # 不带它时，我们等到读超时就断开并重试，而 Atlas 还在让上游继续生成、继续计费
        # ——2026-09-29 chat/deterministic 的 p95 是 94 秒，本地读超时是 90 秒，
        # 恰好有一截调用付了两遍钱。带上它，超时由 Atlas 执行：取消上游、停止计费，
        # 答 504 DEADLINE_EXCEEDED（不可重试）。留 2 秒给响应走回来。
        self._deadline_ms = max(1_000, min(600_000, int(timeout_seconds * 1000) - 2_000))
        self._max_retries = max(0, min(max_retries, 3))
        # 传输层做成可注入的依赖缝：测试要看到<b>真实发出去的字节</b>——
        # 请求体的字段名、tenantId 是不是 UUID、票有没有挂在 Authorization 上——
        # 而打桩到方法级别的测试恰好看不见这些。
        self._transport = transport

    def validate_configuration(self) -> None:
        if not self._base_url:
            raise AiProviderNotConfiguredError("ATLAS_API_URL 未配置")

    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[ResponseModel],
    ) -> AiProviderResult:
        del user  # 归因走票里的 claims，不走调用方自称的字符串
        self.validate_configuration()

        task_id = current_task_id()
        if not task_id:
            raise AtlasTaskIdMissingError(
                "调用 Atlas 缺少 task_id，无法归集本次推理消耗", stage=operation
            )
        token, tenant_id = current_atlas_identity()
        if not token:
            raise AiProviderNotConfiguredError(
                "本次请求没有携带 Atlas S2S 票；票由 Java 侧现铸并转呈",
                stage=operation,
            )

        request = self._request(operation, payload, response_model, task_id, tenant_id)
        # 流式调用。上游模型在非流式模式下要把整段答案生成完才回响应头，而 Atlas 对「等响应头」
        # 只给 30 秒——2026-09-30 正文续写在 23–29 秒的都成功、稍长一点的全部在 30.0 秒
        # PROVIDER_UNAVAILABLE（含备选模型）。流式时上游立刻回头、再逐段送文本，
        # 那 30 秒的门槛不再相关；整次调用仍受 timeoutMs 约束。
        request["stream"] = True
        started = time.monotonic()
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{self._base_url}/v1/chat",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "text/event-stream, application/json",
                        },
                        json=request,
                    ) as streamed:
                        if streamed.status_code >= 400:
                            await streamed.aread()
                            response = streamed
                        else:
                            response = await _collect_stream(streamed)
            except httpx.TimeoutException as exception:
                if attempt >= self._max_retries:
                    raise AiProviderTimeoutError(
                        "Atlas 请求超时",
                        stage=operation,
                        attempts=attempt + 1,
                        elapsed_millis=_elapsed_millis(started),
                    ) from exception
                await asyncio.sleep(2**attempt)
                continue
            except httpx.NetworkError as exception:
                if attempt >= self._max_retries:
                    raise AiProviderError(
                        "Atlas 不可达",
                        stage=operation,
                        attempts=attempt + 1,
                        elapsed_millis=_elapsed_millis(started),
                    ) from exception
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code < 400:
                return self._decode_response(response, operation, attempt + 1)
            # 走到这里的 response 要么是 HTTP 层的拒绝（已读完正文），要么是流中途的
            # error 帧折算出的同形状封套——两者走同一套翻译与重试判断。

            error = _atlas_error(response, operation, attempt + 1, started)
            if _should_retry(error, response) and attempt < self._max_retries:
                await asyncio.sleep(_retry_delay_seconds(response, attempt))
                continue
            raise error

        raise AiProviderError(
            "Atlas 请求失败",
            stage=operation,
            attempts=self._max_retries + 1,
            elapsed_millis=_elapsed_millis(started),
        )

    def _request(
        self,
        operation: str,
        payload: dict[str, Any],
        response_model: type[ResponseModel],
        task_id: str,
        tenant_id: str | None,
    ) -> dict[str, Any]:
        import json

        schema = response_model.model_json_schema(by_alias=True)
        body: dict[str, Any] = {
            "endpointCode": endpoint_for(operation),
            "messages": [
                {"role": "system", "content": _operation_prompt(operation)},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"outputJsonSchema": schema, "input": payload},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "taskId": task_id,
            # 也是 Atlas 侧的幂等键，以及在它请求日志里定位本次调用的唯一办法，
            # 所以在这里生成而不是交给服务端。
            "requestId": str(uuid.uuid4()),
            **_attribution(operation, task_id),
            **self._generation(operation, payload),
        }
        if tenant_id:
            # tenantId 取自票里的 claim，<b>不是</b>产品码。送产品码看起来能跑：
            # Atlas 只校验它非空，而产品授权那条路径在租户断言之前就返回了。
            # 一旦授权缺失或 endpoint 被改指，控制流落到 UUID 断言上，
            # 于是失败表现为 400 INVALID_TENANT_ID——读起来像请求体写错了，
            # 真正的原因被盖住。非 UUID 还会让 Atlas 的请求日志里写进 NULL，
            # 本产品的流量就从每一张租户汇总表里消失，且全程没有任何报错。
            body["tenantId"] = tenant_id
        return body

    def _generation(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        """生成参数：推理开关、温度、输出上限、总时限。

        Atlas v0.7.8 起这些都按调用传（#69）。此前本仓认定「生成参数属于路由配置、
        请求体不带」，而 Atlas 并不给路由设默认温度，推理开关也不按路由区分——于是
        解读环节以上游默认（开推理、默认温度）跑了一整段时间。取值沿用直连时代逐条实测的
        策略表（详细设计 §8.1），与直连 provider 读同一份，不另抄一遍。
        """
        body: dict[str, Any] = {
            "thinking": thinking_for(operation),
            "temperature": _operation_temperature(operation),
            "timeoutMs": self._deadline_ms,
        }
        max_tokens = _operation_max_tokens(operation, payload)
        if max_tokens is not None:
            body["maxTokens"] = max_tokens
        return body

    def _decode_response(
        self, response: httpx.Response, operation: str, attempts: int
    ) -> AiProviderResult:
        content = ""
        finish_reason: str | None = None
        body: dict[str, Any] = {}
        try:
            decoded_body = response.json()
            if not isinstance(decoded_body, dict):
                raise TypeError("Atlas 响应不是对象")
            body = decoded_body
            content = body["message"]["content"]
            finish_reason = body.get("finishReason")
            if not isinstance(content, str):
                raise TypeError("Atlas 返回的内容不是文本")
            decoded = _decode_json_object(content)
        except (KeyError, IndexError, TypeError, ValueError) as exception:
            diagnostics = _atlas_diagnostics(body, content, finish_reason, attempts)
            message = (
                "模型输出在完成 JSON 之前被截断"
                if finish_reason in {"length", "max_tokens"}
                else "模型返回了无法解析的结构化输出"
            )
            raise AiProviderOutputError(
                message,
                raw_output=content,
                finish_reason=finish_reason,
                response_length=len(content),
                response_hash=_text_hash(content),
                input_tokens=diagnostics.input_tokens,
                output_tokens=diagnostics.output_tokens,
                attempts=attempts,
            ) from exception
        del operation
        return AiProviderResult(
            decoded, _atlas_diagnostics(body, content, finish_reason, attempts)
        )


    # ── 系统验证 ─────────────────────────────────────────────────────────────
    #
    # 两个探测走的是与业务调用<b>同一张票、同一个基址、同一套错误翻译</b>，
    # 不另起一条线路：另起的那条证明的只是它自己能通。

    async def list_models(self) -> list[str]:
        """带票读 ``GET /v1/models``。不计量，是「票有效」最便宜的证明。

        200 之后的任何失败都是授权或业务问题，不是凭据问题。
        """
        self.validate_configuration()
        token, _ = current_atlas_identity()
        if not token:
            raise AiProviderNotConfiguredError(
                "本次请求没有携带 Atlas S2S 票；票由 Java 侧现铸并转呈", stage="atlas_models"
            )
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.get(
                    f"{self._base_url}/v1/models",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
        except httpx.HTTPError as exception:
            raise AiProviderError(
                "Atlas 不可达", stage="atlas_models", elapsed_millis=_elapsed_millis(started)
            ) from exception
        if response.status_code >= 400:
            raise _atlas_error(response, "atlas_models", 1, started)
        return _model_codes(response.json())

    async def contract(self) -> dict[str, Any]:
        """带票读 ``GET /.well-known/vxture-contract``，与钉住的指纹比对。不计量。

        指纹是 Atlas 契约（必填规则与错误码词表）的纯函数：它变了，说明 Atlas 改了
        必填项或错误码，要逐条核对后再改钉住的值。这是 Atlas 发版后调用方唯一需要例行做的事。
        """
        self.validate_configuration()
        token, _ = current_atlas_identity()
        if not token:
            raise AiProviderNotConfiguredError(
                "本次请求没有携带 Atlas S2S 票；票由 Java 侧现铸并转呈", stage="atlas_contract"
            )
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.get(
                    f"{self._base_url}/.well-known/vxture-contract",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
        except httpx.HTTPError as exception:
            raise AiProviderError(
                "Atlas 不可达", stage="atlas_contract", elapsed_millis=_elapsed_millis(started)
            ) from exception
        if response.status_code >= 400:
            raise _atlas_error(response, "atlas_contract", 1, started)
        body = response.json()
        fingerprint = body.get("fingerprint") if isinstance(body, dict) else None
        return {
            "fingerprint": fingerprint,
            "pinned": ATLAS_CONTRACT_FINGERPRINT,
            "matches": fingerprint == ATLAS_CONTRACT_FINGERPRINT,
            "errorCodeCount": len(body.get("errorCodes") or []) if isinstance(body, dict) else 0,
        }

    async def route_capacity(self) -> dict[str, Any]:
        """带票读 ``GET /v1/model-routes``，并逐条核对本产品实际使用的路由。不计量。

        三项核对，任一不满足即该路由不通过：

        - ``state`` 为 ``active``；
        - ``thinkingModes`` 包含本产品在这条路由上会发出的每一种模式——不支持时 Atlas 以
          ``422 THINKING_MODE_UNSUPPORTED`` 拒绝这条路由上的<b>每一次</b>调用，运营改指向时
          最可能悄悄打破的就是这一条；
        - ``contextWindow`` 不小于 :data:`REQUIRED_CONTEXT_TOKENS`。

        ``null`` 表示 Atlas 也不知道（#69），如实标为「未知」而不是「通过」。
        """
        self.validate_configuration()
        token, _ = current_atlas_identity()
        if not token:
            raise AiProviderNotConfiguredError(
                "本次请求没有携带 Atlas S2S 票；票由 Java 侧现铸并转呈", stage="atlas_routes"
            )
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.get(
                    f"{self._base_url}/v1/model-routes",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
        except httpx.HTTPError as exception:
            raise AiProviderError(
                "Atlas 不可达", stage="atlas_routes", elapsed_millis=_elapsed_millis(started)
            ) from exception
        if response.status_code >= 400:
            raise _atlas_error(response, "atlas_routes", 1, started)
        return _evaluate_routes(response.json())

    async def probe(self, endpoint_code: str) -> dict[str, Any]:
        """对一条路由发一次最短的真实调用。<b>会花钱</b>，由 Atlas 自行计量上报。

        补全上限压到 8 个 token：要证明的是这条路由授权在、模型挂着、
        计量链路活着，不是模型会说什么。失败不抛出而是写进结果——
        逐条探测时一条路由未授权不该遮住其余几条的真相。
        """
        self.validate_configuration()
        task_id = current_task_id()
        token, tenant_id = current_atlas_identity()
        if not task_id or not token:
            return {
                "endpointCode": endpoint_code,
                "ok": False,
                "code": "AI_TASK_ID_MISSING" if not task_id else "AI_PROVIDER_NOT_CONFIGURED",
                "message": "缺少 task_id" if not task_id else "本次请求没有携带 Atlas S2S 票",
            }
        body: dict[str, Any] = {
            "endpointCode": endpoint_code,
            "messages": [{"role": "user", "content": "ping"}],
            "maxTokens": 8,
            # 关推理是这个探测成立的前提：DeepSeek 默认开推理，8 个 token 会全部花在
            # 推理上，主模型一个字都没答——那时看到的「通过」是备选模型替它答的
            # （Atlas #69 走查，2026-09-29）。温度 0 让结果可复现。
            "thinking": "off",
            "temperature": 0,
            "timeoutMs": self._deadline_ms,
            "taskId": task_id,
            "requestId": str(uuid.uuid4()),
            **_attribution("diagnostics.atlas_probe", task_id),
        }
        if tenant_id:
            body["tenantId"] = tenant_id
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(
                    f"{self._base_url}/v1/chat",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    json=body,
                )
        except httpx.HTTPError as exception:
            return {
                "endpointCode": endpoint_code,
                "ok": False,
                "code": "AI_GATEWAY_UNAVAILABLE",
                "message": f"Atlas 不可达：{type(exception).__name__}",
            }
        if response.status_code >= 400:
            error = _atlas_error(response, "atlas_probe", 1, started)
            return {
                "endpointCode": endpoint_code,
                "ok": False,
                "code": getattr(error, "atlas_code", error.code),
                "message": str(error),
            }
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            payload = {}
        usage = payload.get("usage")
        message = payload.get("message")
        reasoning = message.get("reasoning") if isinstance(message, dict) else None
        thinking = payload.get("thinking")
        # Atlas 承诺「不会悄悄忽略请求的模式」；这里把它的回显和实际有没有推理内容
        # 一并核对。回显不是 off、或带 off 仍返回推理内容，都算这条路由没通过——
        # 那意味着解读类环节的推理成本还在。
        honoured = thinking == "off" and not reasoning
        return {
            "endpointCode": endpoint_code,
            "ok": honoured,
            "modelCode": payload.get("modelCode"),
            "latencyMs": payload.get("latencyMs"),
            "totalTokens": usage.get("totalTokens") if isinstance(usage, dict) else None,
            "thinking": thinking,
            "reasoningReturned": bool(reasoning),
            **(
                {}
                if honoured
                else {
                    "code": "AI_THINKING_NOT_HONOURED",
                    "message": f"请求 thinking=off，Atlas 回显 {thinking!r}"
                    + ("，且返回了推理内容" if reasoning else ""),
                }
            ),
        }


#: applicationId 的命名空间。固定值：同一个 task_id 在任何进程、任何时刻都得到同一个 id。
_APPLICATION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://tenderforge.vxture.com/atlas/application")


def _attribution(feature_id: str, task_id: str) -> dict[str, str]:
    """Atlas 用来拆分消耗的三个字段，<b>必须一起送</b>。

    ``applicationType`` 固定为 ``agent``——本产品是一个智能体实例。
    ``featureId`` 是 operation 本身：请求体里没有别的维度能说明这一笔推理花在
    解读、目录、正文还是审查上。

    ``applicationId`` 是 Atlas 的默认计量分组轴，两条硬约束都是生产上撞出来的：
    送了 ``applicationType`` 就必须送它，否则每一次调用都是
    ``400 APPLICATION_ID_REQUIRED``（2026-09-29 v0.1.20，全部模型调用中断）；
    它又必须是 UUID——Atlas 的授权查询按 UUID 转型，送 operation 名会以数据库转型错误失败
    （yucer 2026-09-28）。所以从 task_id 派生 UUIDv5：同一个任务的所有调用归到同一个
    application 下，与 taskId 这个跨产品聚合键一一对应，而且构造上永远是合法 UUID。
    """
    return {
        "applicationType": "agent",
        "applicationId": str(uuid.uuid5(_APPLICATION_NAMESPACE, task_id)),
        "featureId": feature_id,
    }


def _evaluate_routes(body: Any) -> dict[str, Any]:
    listed: dict[str, dict[str, Any]] = {}
    if isinstance(body, dict):
        for item in body.get("endpoints") or []:
            if isinstance(item, dict) and isinstance(item.get("endpointCode"), str):
                listed[item["endpointCode"]] = item
    routes: list[dict[str, Any]] = []
    for code, modes in sorted(route_requirements().items()):
        item = listed.get(code)
        if item is None:
            routes.append({"endpointCode": code, "ok": False, "problems": ["路由列表里没有这条路由"]})
            continue
        problems: list[str] = []
        unknown: list[str] = []
        if item.get("state") != "active":
            problems.append(f"state={item.get('state')!r}")
        supported = item.get("thinkingModes")
        if isinstance(supported, list):
            missing = sorted(modes - {str(mode) for mode in supported})
            if missing:
                problems.append(f"不支持推理模式 {', '.join(missing)}（本产品会发出）")
        else:
            unknown.append("thinkingModes")
        window = item.get("contextWindow")
        if isinstance(window, int):
            if window < REQUIRED_CONTEXT_TOKENS:
                problems.append(f"上下文窗口 {window} < 所需 {REQUIRED_CONTEXT_TOKENS}")
        else:
            unknown.append("contextWindow")
        routes.append({
            "endpointCode": code,
            "ok": not problems,
            "state": item.get("state"),
            "contextWindow": window,
            "maxOutputTokens": item.get("maxOutputTokens"),
            "thinkingModes": supported,
            "requiredThinking": sorted(modes),
            "problems": problems,
            "unknown": unknown,
        })
    max_bytes = body.get("maxRequestBytes") if isinstance(body, dict) else None
    return {"maxRequestBytes": max_bytes, "routes": routes}


def _model_codes(body: Any) -> list[str]:
    """``/v1/models`` 的三种已见形状：裸数组、``{data: [...]}``、``{models: [...]}``。"""
    items: Any = body
    if isinstance(body, dict):
        items = body.get("data") or body.get("models") or []
    if not isinstance(items, list):
        return []
    codes: list[str] = []
    for item in items:
        if isinstance(item, str):
            codes.append(item)
        elif isinstance(item, dict):
            code = item.get("modelCode") or item.get("code") or item.get("id")
            if isinstance(code, str):
                codes.append(code)
    return codes

async def _collect_stream(response: httpx.Response) -> httpx.Response:
    """把 Atlas 的 SSE 帧收成与非流式同形状的响应，交给同一套解码与错误翻译。

    帧：``text``（增量）、``done``（用量与 finishReason）、``error``（中途失败，
    状态码此时已是 200 且不会再变）。``UPSTREAM_FRAME_UNPARSEABLE`` 是 Atlas 注明
    「流会继续」的唯一错误码，跳过；其余 error 帧折算成 X-1 封套。
    没收到 ``done`` 就结束的流按「不完整」处理——把半截答案当完整答案用是最坏的结局。
    其他帧类型（例如推理增量）忽略：正文只取 ``text``。
    """
    if "text/event-stream" not in response.headers.get("content-type", ""):
        # 被调方没有按流回答（例如按 JSON 一次性给出）：原样读完，按非流式解码。
        await response.aread()
        return response
    parts: list[str] = []
    done: dict[str, Any] | None = None
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data:
            continue
        if data == "[DONE]":
            break
        try:
            frame = json.loads(data)
        except ValueError:
            continue
        if not isinstance(frame, dict):
            continue
        kind = frame.get("type")
        if kind == "text" and isinstance(frame.get("delta"), str):
            parts.append(frame["delta"])
        elif kind == "done":
            done = frame
            break
        elif kind == "error":
            if frame.get("code") == "UPSTREAM_FRAME_UNPARSEABLE":
                continue
            return httpx.Response(502, json={
                "code": frame.get("code") or "UNKNOWN",
                "message": frame.get("message") or "Atlas 流中途失败",
                **({"retryable": frame["retryable"]} if isinstance(frame.get("retryable"), bool) else {}),
            })
    if done is None:
        return httpx.Response(502, json={
            "code": "STREAM_INCOMPLETE",
            "message": "Atlas 的流在 done 帧之前结束，答案不完整",
            "retryable": True,
        })
    return httpx.Response(200, json={
        "message": {"role": "assistant", "content": "".join(parts)},
        "finishReason": done.get("finishReason"),
        "usage": done.get("usage") or {},
        "thinking": done.get("thinking"),
        # done 帧报的是实际应答的模型，故障转移后是兜底模型（Atlas v0.4.0 起）。
        "modelCode": done.get("modelCode"),
    })


def _atlas_diagnostics(
    body: dict[str, Any], content: str, finish_reason: str | None, attempts: int
) -> AiProviderDiagnostics:
    """把 Atlas 回报的用量与实际模型原样带回（Atlas 口径，v0.7.13 起各厂商一致）。

    ``promptTokens`` 是全部输入，``cachedInputTokens`` 是其中读缓存的部分；
    ``reasoningTokens`` 是 ``completionTokens`` 的子集。子集字段缺席 = 上游没报，记空而不是 0。
    上游没报用量时 Atlas 返回的是三个 0 而内部记 NULL——把这些 0 当成真实用量累加会让消耗
    被低估且看起来一切正常，所以总量为 0 时一概按「没报」处理。
    """
    usage = body.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    total = usage.get("totalTokens")
    reported = isinstance(total, int) and total > 0

    def count(key: str) -> int | None:
        value = usage.get(key)
        return value if reported and isinstance(value, int) and value >= 0 else None

    model_code = body.get("modelCode")
    return AiProviderDiagnostics(
        finish_reason=finish_reason,
        response_length=len(content),
        response_hash=_text_hash(content),
        input_tokens=count("promptTokens"),
        output_tokens=count("completionTokens"),
        reasoning_tokens=count("reasoningTokens"),
        cached_input_tokens=count("cachedInputTokens"),
        attempts=attempts,
        model_code=model_code if isinstance(model_code, str) and model_code else None,
    )


def _atlas_error(
    response: httpx.Response, operation: str, attempts: int, started: float
) -> AiProviderError:
    """把 Atlas 的错误信封翻成本服务的异常。

    ``/v1`` 现在统一是 ``{code, message, retryable}``（通则 X-1）。
    ``UNKNOWN`` 是给「身体根本不是 JSON」——代理页面、被截断的响应——留的地板，
    不是我们预期的第二种形状。
    """
    envelope: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            envelope = parsed
    except ValueError:
        envelope = {}
    code = str(envelope.get("code") or "UNKNOWN")
    message = envelope.get("message")
    if isinstance(message, list):
        message = "; ".join(str(item) for item in message)
    message = str(message) if message else f"Atlas 返回 HTTP {response.status_code}"
    elapsed = _elapsed_millis(started)

    if response.status_code == 401 or code in {"S2S_TOKEN_INVALID", "UNAUTHORIZED"}:
        return AtlasTokenRejectedError(
            message, stage=operation, attempts=attempts, elapsed_millis=elapsed
        )
    if code == "NOT_ENTITLED":
        return AtlasNotEntitledError(
            f"{message}（本产品尚未被授权路由到该 endpoint）",
            stage=operation,
            attempts=attempts,
            elapsed_millis=elapsed,
        )
    if response.status_code == 403:
        return AiProviderAuthenticationError(
            message, stage=operation, attempts=attempts, elapsed_millis=elapsed
        )
    if code in _INPUT_TOO_LARGE_CODES:
        error: AiProviderError = AtlasInputTooLargeError(
            f"输入超出上限（{code}）：{message}",
            stage=operation,
            attempts=attempts,
            elapsed_millis=elapsed,
        )
        error.atlas_code = code  # type: ignore[attr-defined]
        return error
    if code == "OUTPUT_BUDGET_EXHAUSTED":
        error = AtlasOutputBudgetExhaustedError(
            f"输出预算被推理用完（{code}）：{message}",
            stage=operation,
            attempts=attempts,
            elapsed_millis=elapsed,
        )
        error.atlas_code = code  # type: ignore[attr-defined]
        return error
    if response.status_code in {408, 504} or code in {"UPSTREAM_TIMEOUT", "DEADLINE_EXCEEDED"}:
        return AiProviderTimeoutError(
            message, stage=operation, attempts=attempts, elapsed_millis=elapsed
        )
    error = AiProviderError(
        f"{code}: {message}", stage=operation, attempts=attempts, elapsed_millis=elapsed
    )
    error.atlas_code = code  # type: ignore[attr-defined]
    return error


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    """限流时照 Atlas 给的 ``retryAfterMs`` 等（v0.7.11 起才真的带上），其余按指数退避。

    上限 30 秒：等待发生在一次模型调用的预算里，等得更久就该交给 Temporal 的重试。
    只有技术限流带这个值，所以先判空。
    """
    try:
        envelope = response.json()
    except ValueError:
        envelope = {}
    wait = envelope.get("retryAfterMs") if isinstance(envelope, dict) else None
    if isinstance(wait, int | float) and wait > 0:
        return min(float(wait) / 1000, 30.0)
    return float(2**attempt)


def _should_retry(error: AiProviderError, response: httpx.Response) -> bool:
    """退避重试是否可能有用。

    优先级：被调方自己的答案 > 本地码表 > 状态码。<b>永不从状态码推断</b>
    在前两者能回答时的情形——一个商业上限可能以 429 到达而绝不该被重试，
    一个 501 落在 5xx 区间里却同样绝不该被重试。

    401 三处都不在，是刻意的：重铸再调是标准的令牌处理，
    和这里描述的退避是两件不同的事，而且它由 Java 侧完成。
    """
    if isinstance(error, AtlasTokenRejectedError | AtlasNotEntitledError):
        return False
    envelope: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            envelope = parsed
    except ValueError:
        envelope = {}
    declared = envelope.get("retryable")
    if isinstance(declared, bool):
        return declared
    known = _RETRYABLE_CODES.get(str(envelope.get("code") or ""))
    if known is not None:
        return known
    return response.status_code in {408, 429, 500, 502, 503, 504}
