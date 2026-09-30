# GENERATED_BY_AI
# MODEL: claude-opus-5
# DATE: 2026-09-08
"""平台统一错误封套（产品接入通则 X-1）。

FastAPI 默认用 ``{"detail": ...}`` 作答，那是<b>第二种信封形状</b>：没有 ``code``，
没有 ``retryable``，调用方只能回去按状态码猜。本模块把这一面收敛成和 Java 侧
完全一致的四字段封套——被调方是内部服务不构成豁免，"承载位置随传输，封套内容统一"
说的正是这件事。
"""

from __future__ import annotations

from typing import Any

# 会自愈的失败：上游或依赖此刻不可用，原样重发有意义。
# 判据只有一条——同一个请求过一会儿会不会成功。需要人改配置、改载荷的都不算，
# 所以 AI_PROVIDER_NOT_CONFIGURED 和 AI_OUTPUT_INVALID 刻意不在表内。
RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        "AI_PROVIDER_ERROR",
        "AI_MODEL_TIMEOUT",
        "AI_MODEL_AUTH_FAILED",
        # Atlas 拒了这张票。可重试，但重试的方式是<b>由 Java 侧重铸</b>：
        # 这个服务不铸票，原样再送一遍同一张必然再被拒。
        "AI_ATLAS_TOKEN_REJECTED",
        "PARSER_UNAVAILABLE",
        "DOCUMENT_RENDER_UNAVAILABLE",
        "INTERNAL_ERROR",
    }
)


class ServiceError(Exception):
    """一个带契约字段的失败。

    ``retryable`` 默认由 :data:`RETRYABLE_CODES` 按码派生，而不是在每个抛出点
    各写一个布尔——集中一处才能被评审。需要覆盖时显式传入。
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        *,
        retryable: bool | None = None,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = code in RETRYABLE_CODES if retryable is None else retryable
        self.field = field
        self.details = details or {}


def envelope(
    code: str,
    message: str,
    retryable: bool,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造封套。

    ``field`` 为空时整体省略而不是置 ``None``——一个恒为 null 的键会让调用方
    以为它有时候有值，然后写一条永远不进的分支。

    ``details`` 是 X-1 四个字段之外的诊断：失败阶段、耗时、尝试次数、finish_reason、
    token 与结构校验错误。Java 侧把它们落进 ``bid_ai_run_attempt``。它曾经只挂在异常对象上
    而从不序列化，Java 读的又是 FastAPI 旧的 ``{"detail": …}``——两头都不报错，
    结果是每一次 AI 失败都只剩一句「AI 工作流执行失败」，定位全靠读对方进程日志。
    """
    body: dict[str, Any] = {"code": code, "message": message, "retryable": retryable}
    if field is not None:
        body["field"] = field
    if details:
        body["details"] = details
    return body
