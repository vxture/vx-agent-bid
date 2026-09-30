# GENERATED_BY_AI
# MODEL: claude-opus-5
# DATE: 2026-09-14
"""operation 到 Atlas endpointCode 的<b>唯一映射点</b>。

Atlas 的 ``POST /v1/chat`` 请求体只有
``{endpointCode, messages, tenantId, taskId, requestId}``——没有 temperature、
没有 max_tokens、没有 thinking 开关。生成参数属于 endpoint 的配置，不属于调用方；
产品这一侧能决定的只有「这一次调用走哪条路由」。

**Atlas 授予本产品十条通用路由**（owner 2026-09-29）：六条 chat、两条 embedding、
两条 rerank。本产品只路由其中四条 chat：
``chat/deterministic`` / ``chat/fast`` / ``chat/default`` / ``chat/reasoning``。
其余六条（``chat/extract`` / ``chat/vision`` / ``embedding/*`` / ``rerank/*``）
授权在手但没有调用点——``chat/extract`` 的生成参数未经本产品实测，按名字把抽取类
operation 挪过去就是「按路由名字猜」，下面的分档规则明令不做。
2026-09-11 请求六个专属 endpoint 的联络函已被取代，见 ``docs/80-liaison``。

产品命名任务，运营决定每条路由挂哪个模型——改指向不需要发版。所以这里
<b>只写任务到路由的对应</b>：不写模型名，也不开环境变量覆盖。一份可以被覆盖的
映射就是第二个来源，而线上跑的是哪一份，从代码里再也看不出来。

**分档依据是直连时代逐条实测出来的策略**（详细设计 §8.1），不是按路由名字猜。
按下面的顺序取第一条命中的：

1. 当时开 thinking 的 → ``chat/reasoning``
2. 当时温度为 0 的 → ``chat/deterministic``
3. 当时走 Quality 模型、关 thinking 的 → ``chat/default``
4. 其余（Fast 模型、关 thinking、温度大于 0）→ ``chat/fast``

顺序有含义：一致性审查温度也是 0，但它首先是一件没有推理做不了的事。
这条规则由测试从直连 provider 的策略表反推并逐条比对——两边任何一边改了而另一边
没跟上，测试会红。
"""

from __future__ import annotations

from dataclasses import dataclass

DETERMINISTIC_ENDPOINT_CODE = "chat/deterministic"
FAST_ENDPOINT_CODE = "chat/fast"
DEFAULT_ENDPOINT_CODE = "chat/default"
REASONING_ENDPOINT_CODE = "chat/reasoning"

#: Atlas 授予本产品的全部路由（owner 2026-09-29，与 Atlas 侧授权逐条一致）。
#: 映射里出现这之外的 code，对应 operation 的每一次调用都是 ``403 NOT_ENTITLED``，
#: 与令牌是否有效无关。
AUTHORIZED_ENDPOINT_CODES = frozenset(
    {
        "chat/default",
        "chat/deterministic",
        "chat/extract",
        "chat/fast",
        "chat/reasoning",
        "chat/vision",
        "embedding/default",
        "embedding/quality",
        "rerank/default",
        "rerank/quality",
    }
)


@dataclass(frozen=True)
class OperationRoute:
    endpoint_code: str
    note: str


#: 逐 operation 的路由。**键集合必须等于服务里真实发起调用的 operation 全集**
#: ——测试从源码里扫出每一处 ``execute_result("<operation>", ...)`` 来比对。
#: 这份表曾经漏过两个活的 operation（策略规划与分支蓝图），它们静默落到了兜底
#: 路由上，而当时的测试手写着「八个全部登记」，于是一起放行了。
OPERATION_ROUTES: dict[str, OperationRoute] = {
    # ── chat/deterministic：事实搬运，任何随机性都是噪声 ─────────────────
    "project_overview_source_selection": OperationRoute(
        DETERMINISTIC_ENDPOINT_CODE, "从整份招标文件里挑证据片段，只返回 id 列表"
    ),
    "project_overview_extraction": OperationRoute(
        DETERMINISTIC_ENDPOINT_CODE, "抽取项目概述，不允许发挥"
    ),
    "technical_scoring_extraction": OperationRoute(
        DETERMINISTIC_ENDPOINT_CODE, "评分条款排序，改一个分值标书直接作废"
    ),
    # ── chat/fast：量大、关 thinking ──────────────────────────────────────
    "outline_branch_expansion": OperationRoute(
        FAST_ENDPOINT_CODE, "三级目录分批展开，一份大标书十几批；结构已由骨架定下"
    ),
    "chapter_drafting": OperationRoute(
        FAST_ENDPOINT_CODE, "正文续写，调用次数占全流程绝大多数，单价决定一份标书的成本"
    ),
    # ── chat/default：要质量，但刻意不开 thinking ─────────────────────────
    "outline_skeleton_planning": OperationRoute(
        DEFAULT_ENDPOINT_CODE, "一二级骨架一次定生死；要一次吐出上万 token，推理会挤占补全预算"
    ),
    "section_revision": OperationRoute(
        DEFAULT_ENDPOINT_CODE, "受约束改写；补全预算要留给替换正文本身"
    ),
    # ── chat/reasoning：没有推理做不了 ────────────────────────────────────
    "bid_strategy_planning": OperationRoute(
        REASONING_ENDPOINT_CODE, "给每条评分响应编 SP-00N——目录与评分表之间唯一的可追溯连接"
    ),
    "branch_blueprint_planning": OperationRoute(
        REASONING_ENDPOINT_CODE, "决定同一分支下各章各写什么、不写什么，防相邻章节大面积重复"
    ),
    "consistency_review": OperationRoute(
        REASONING_ENDPOINT_CODE, "全文找矛盾、评分点缺口与编造的承诺和资质"
    ),
}


#: 本产品单次调用最大输入的保守 token 估计，用于核对路由窗口放不放得下。
#:
#: 最大的单次输入是概述选段与审查的一个窗口（≤ 60,000 字）加提示词、Schema 与共享上下文。
#: 按「一字一 token」的上界估算——中文在各家分词下通常更少——再留约 20K 给输出与余量。
#: 这是核对用的下限，不是出站前的拦截：窗口超限由 Atlas 以 CONTEXT_LENGTH_EXCEEDED 答复，
#: 网关不预估 token（Atlas #69），产品侧也不去预估。
REQUIRED_CONTEXT_TOKENS = 80_000


def route_requirements() -> dict[str, set[str]]:
    """每条实际路由上本产品会发出的推理模式。"""
    modes: dict[str, set[str]] = {}
    for operation, route in OPERATION_ROUTES.items():
        modes.setdefault(route.endpoint_code, set()).add(thinking_for(operation))
    return modes


def thinking_for(operation: str) -> str:
    """这次调用开不开推理：走 ``chat/reasoning`` 的开，其余一律关。

    Atlas v0.7.8 起推理开关按调用传（``thinking: "off" | "on"``），<b>不传就用上游默认，
    而默认通常是开</b>。``chat/deterministic`` 与 ``chat/reasoning`` 的主模型是同一个
    DeepSeek v4-pro——推理从来不是由路由区分的。不传的代价已经实测：2026-09-29 解读环节
    平均每次输出 4137 token，其中 78% 是推理，p95 延迟 94 秒（Atlas #69）。

    与路由同源而不另立一张表：路由本来就是按直连时代的 thinking 策略分出来的
    （见模块说明），开推理的 operation 恰好就是走 ``chat/reasoning`` 的那三个。
    """
    return "on" if endpoint_for(operation) == REASONING_ENDPOINT_CODE else "off"


def endpoint_for(operation: str) -> str:
    """这次调用该路由到哪个 endpoint。

    未登记的 operation 落到 ``chat/default`` 而不是抛异常：线上多出一个 operation
    时让它能跑，比让那个环节整体失败要好。漏登记这件事由测试在合并前拦下，
    不靠运行时报错。
    """
    route = OPERATION_ROUTES.get(operation)
    return route.endpoint_code if route else DEFAULT_ENDPOINT_CODE


def routed_endpoint_codes() -> tuple[str, ...]:
    """本产品真正会调用的路由，按字母序去重。

    系统验证的 Atlas 探测逐条打这几条：授权清单里的其余路由没有调用点，
    探它们证明不了本产品任何一条业务链路是通的。
    """
    return tuple(sorted({route.endpoint_code for route in OPERATION_ROUTES.values()}))
