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
    _operation_prompt,
    _text_hash,
)
from czghagent_ai.services.atlas_endpoints import endpoint_for
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
}

#: Atlas 自己的上游首字节超时是 30 秒，且主模型超时后可能再试 endpoint 的备选，
#: 所以一次调用合法地超过 60 秒。这个上限是留给 Atlas 把话说完的——
#: 卡得更短只会把它结构化的失败换成一个我们这一侧看不懂的连接中断。
_DEFAULT_TIMEOUT_SECONDS = 90.0


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
        started = time.monotonic()
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    response = await client.post(
                        f"{self._base_url}/v1/chat",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/json",
                        },
                        json=request,
                    )
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

            error = _atlas_error(response, operation, attempt + 1, started)
            if _should_retry(error, response) and attempt < self._max_retries:
                await asyncio.sleep(2**attempt)
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
        usage = payload.get("usage") if isinstance(payload, dict) else None
        return {
            "endpointCode": endpoint_code,
            "ok": True,
            "modelCode": payload.get("modelCode") if isinstance(payload, dict) else None,
            "latencyMs": payload.get("latencyMs") if isinstance(payload, dict) else None,
            "totalTokens": usage.get("totalTokens") if isinstance(usage, dict) else None,
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

def _atlas_diagnostics(
    body: dict[str, Any], content: str, finish_reason: str | None, attempts: int
) -> AiProviderDiagnostics:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    total = usage.get("totalTokens")
    # 上游没报用量时 Atlas 返回的是三个 0，而它自己内部记的是 NULL。
    # 把这些 0 当成真实用量累加会让消耗被低估，且看起来一切正常——
    # 「这次调用没花 token」和「这次调用花了多少没人知道」是两件事。
    reported = isinstance(total, int) and total > 0
    return AiProviderDiagnostics(
        finish_reason=finish_reason,
        response_length=len(content),
        response_hash=_text_hash(content),
        input_tokens=usage.get("promptTokens") if reported else None,
        output_tokens=usage.get("completionTokens") if reported else None,
        attempts=attempts,
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
    if response.status_code in {408, 504} or code == "UPSTREAM_TIMEOUT":
        return AiProviderTimeoutError(
            message, stage=operation, attempts=attempts, elapsed_millis=elapsed
        )
    error = AiProviderError(
        f"{code}: {message}", stage=operation, attempts=attempts, elapsed_millis=elapsed
    )
    error.atlas_code = code  # type: ignore[attr-defined]
    return error


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
