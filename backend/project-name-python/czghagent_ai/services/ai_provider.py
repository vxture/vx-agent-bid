# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-28
import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel

from czghagent_ai.model_config import AiModelRequestDialect


class AiProviderError(RuntimeError):
    code = "AI_PROVIDER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        stage: str = "",
        attempts: int | None = None,
        elapsed_millis: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.attempts = attempts
        self.elapsed_millis = elapsed_millis

    def details(self) -> dict[str, object]:
        detail: dict[str, object] = {
            "code": self.code,
            "message": str(self),
            "stage": self.stage,
            "attempts": self.attempts,
            "elapsedMillis": self.elapsed_millis,
        }
        # 被调方（Atlas）自己的码。本服务的码是它的归类，排查时要的是原码。
        atlas_code = getattr(self, "atlas_code", None)
        if atlas_code:
            detail["atlasCode"] = atlas_code
        return detail

    def with_context(self, stage: str, elapsed_millis: int) -> "AiProviderError":
        if not self.stage:
            self.stage = stage
        if self.elapsed_millis is None:
            self.elapsed_millis = elapsed_millis
        return self


class AiProviderNotConfiguredError(AiProviderError):
    code = "AI_PROVIDER_NOT_CONFIGURED"


class AiProviderAuthenticationError(AiProviderError):
    code = "AI_MODEL_AUTH_FAILED"


class AiProviderTimeoutError(AiProviderError):
    code = "AI_MODEL_TIMEOUT"


class AiProviderOutputError(AiProviderError):
    code = "AI_OUTPUT_INVALID"

    def __init__(
        self,
        message: str,
        *,
        raw_output: str = "",
        finish_reason: str | None = None,
        response_length: int = 0,
        response_hash: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        reasoning_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message, attempts=attempts)
        self.raw_output = raw_output
        self.finish_reason = finish_reason
        self.response_length = response_length
        self.response_hash = response_hash
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.reasoning_tokens = reasoning_tokens
        self.cached_input_tokens = cached_input_tokens

    def details(self) -> dict[str, object]:
        detail = super().details()
        detail.update({
            "finishReason": self.finish_reason,
            "responseLength": self.response_length,
            "responseHash": self.response_hash,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "reasoningTokens": self.reasoning_tokens,
            "cachedInputTokens": self.cached_input_tokens,
        })
        return detail

    def diagnostics(self) -> "AiProviderDiagnostics":
        return AiProviderDiagnostics(
            finish_reason=self.finish_reason,
            response_length=self.response_length,
            response_hash=self.response_hash or _text_hash(self.raw_output),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            reasoning_tokens=self.reasoning_tokens,
            cached_input_tokens=self.cached_input_tokens,
            attempts=self.attempts or 1,
        )


@dataclass(frozen=True)
class AiProviderDiagnostics:
    finish_reason: str | None
    response_length: int
    response_hash: str
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None
    attempts: int = 1


@dataclass(frozen=True)
class AiProviderResult:
    data: dict[str, Any]
    diagnostics: AiProviderDiagnostics


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class TenderAiProvider(Protocol):
    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[ResponseModel],
    ) -> AiProviderResult | dict[str, Any]: ...


class ConfigurableTenderAiProvider(TenderAiProvider, Protocol):
    """进程真正选用的模型出口：除了调用，还能不发请求地自检配置（``/ready`` 用它）。

    自检不放进 ``TenderAiProvider``：服务只需要 ``run``，测试替身也只实现 ``run``。
    """

    def validate_configuration(self) -> None: ...


class OpenAiCompatibleProvider:
    _retryable_statuses = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        thinking_disabled_operations: frozenset[str] | None = None,
        quality_model: str | None = None,
        thinking_enabled_operations: frozenset[str] | None = None,
        request_dialect: AiModelRequestDialect = AiModelRequestDialect.DEEPSEEK,
        thinking_budget_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._fast_model = model
        self._quality_model = quality_model or model
        self._timeout = httpx.Timeout(timeout_seconds, connect=30.0)
        self._max_retries = max(0, min(max_retries, 3))
        self._request_dialect = request_dialect
        self._thinking_budget_tokens = max(0, min(thinking_budget_tokens, 32768))
        self._thinking_disabled_operations = (
            thinking_disabled_operations
            if thinking_disabled_operations is not None
            else frozenset({
                "project_overview_source_selection",
                "project_overview_extraction",
                "technical_scoring_extraction",
                "outline_skeleton_planning",
                "outline_branch_expansion",
                "chapter_drafting",
            })
        )
        self._thinking_enabled_operations = (
            thinking_enabled_operations
            if thinking_enabled_operations is not None
            else frozenset({
                "bid_strategy_planning",
                "branch_blueprint_planning",
                "section_revision",
                "consistency_review",
            })
        )

    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[ResponseModel],
    ) -> AiProviderResult:
        del user
        self.validate_configuration()
        request = self._request(operation, payload, response_model)
        started = time.monotonic()
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=request,
                    )
            except httpx.TimeoutException as exception:
                if attempt >= self._max_retries:
                    raise AiProviderTimeoutError(
                        "AI model request timed out",
                        stage=operation,
                        attempts=attempt + 1,
                        elapsed_millis=_elapsed_millis(started),
                    ) from exception
                await asyncio.sleep(2**attempt)
                continue
            except httpx.NetworkError as exception:
                if attempt >= self._max_retries:
                    raise AiProviderError(
                        "AI model request is unavailable",
                        stage=operation,
                        attempts=attempt + 1,
                        elapsed_millis=_elapsed_millis(started),
                    ) from exception
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code in {401, 403}:
                raise AiProviderAuthenticationError(
                    "AI model credentials were rejected",
                    stage=operation,
                    attempts=attempt + 1,
                    elapsed_millis=_elapsed_millis(started),
                )
            if response.status_code in self._retryable_statuses and attempt < self._max_retries:
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code in {408, 504}:
                raise AiProviderTimeoutError(
                    f"AI model failed with HTTP {response.status_code}",
                    stage=operation,
                    attempts=attempt + 1,
                    elapsed_millis=_elapsed_millis(started),
                )
            if response.status_code >= 400:
                raise AiProviderError(
                    f"AI model failed with HTTP {response.status_code}",
                    stage=operation,
                    attempts=attempt + 1,
                    elapsed_millis=_elapsed_millis(started),
                )
            return self._decode_response(response, attempt + 1)
        raise AiProviderError(
            "AI model request failed",
            stage=operation,
            attempts=self._max_retries + 1,
            elapsed_millis=_elapsed_millis(started),
        )

    def _request(
        self,
        operation: str,
        payload: dict[str, Any],
        response_model: type[ResponseModel],
    ) -> dict[str, Any]:
        schema = response_model.model_json_schema(by_alias=True)
        request: dict[str, Any] = {
            "model": self._model_for(operation),
            "temperature": _operation_temperature(operation),
            "response_format": {"type": "json_object"},
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
        }
        max_tokens = _operation_max_tokens(operation, payload)
        if max_tokens is not None:
            request["max_tokens"] = max_tokens
        self._apply_thinking_policy(request, operation, payload)
        return request

    def _apply_thinking_policy(
        self, request: dict[str, Any], operation: str, payload: dict[str, Any]
    ) -> None:
        enabled: bool | None = None
        if operation in self._thinking_disabled_operations:
            enabled = False
        elif operation in self._thinking_enabled_operations:
            enabled = True
        if operation == "section_revision":
            # Constrained rewrites need the completion budget for replacement HTML.
            enabled = False
        if enabled is None or self._request_dialect is AiModelRequestDialect.OPENAI:
            return
        if self._request_dialect is AiModelRequestDialect.DASHSCOPE:
            request["enable_thinking"] = enabled
            budget = _operation_thinking_budget(
                operation, self._thinking_budget_tokens
            )
            if enabled and budget:
                request["thinking_budget"] = budget
            return
        request["thinking"] = {"type": "enabled" if enabled else "disabled"}

    def _model_for(self, operation: str) -> str:
        return self._quality_model if operation in _QUALITY_OPERATIONS else self._fast_model

    def validate_configuration(self) -> None:
        """
        Validate model credentials without sending them to an external service.

        Preconditions:
            - AI_MODEL_API_KEY is expected to contain the provider credential.
        Side Effects:
            - None.
        Error Semantics:
            - AiProviderNotConfiguredError: the environment value is empty.
        """
        if not self._api_key:
            raise AiProviderNotConfiguredError(
                "AI model API key environment variable is empty"
            )

    def _decode_response(
        self, response: httpx.Response, attempts: int = 1
    ) -> AiProviderResult:
        content = ""
        finish_reason: str | None = None
        body: dict[str, Any] = {}
        try:
            decoded_body = response.json()
            if not isinstance(decoded_body, dict):
                raise TypeError("model response is not an object")
            body = decoded_body
            content = body["choices"][0]["message"]["content"]
            finish_reason = body["choices"][0].get("finish_reason")
            if not isinstance(content, str):
                raise TypeError("model content is not text")
            decoded = _decode_json_object(content)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exception:
            diagnostics = _response_diagnostics(body, content, finish_reason, attempts)
            message = (
                "AI model output was truncated before completing JSON"
                if finish_reason in {"length", "max_tokens"}
                else "AI model returned an invalid structured output"
            )
            raise AiProviderOutputError(
                message,
                raw_output=content,
                finish_reason=finish_reason,
                response_length=len(content),
                response_hash=_text_hash(content),
                input_tokens=diagnostics.input_tokens,
                output_tokens=diagnostics.output_tokens,
                reasoning_tokens=diagnostics.reasoning_tokens,
                cached_input_tokens=diagnostics.cached_input_tokens,
                attempts=attempts,
            ) from exception
        return AiProviderResult(
            decoded,
            _response_diagnostics(body, content, finish_reason, attempts),
        )


def _response_diagnostics(
    body: dict[str, Any], content: str, finish_reason: str | None, attempts: int
) -> AiProviderDiagnostics:
    usage = body.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    prompt_details = usage.get("prompt_tokens_details", {})
    completion_details = usage.get("completion_tokens_details", {})
    return AiProviderDiagnostics(
        finish_reason=finish_reason,
        response_length=len(content),
        response_hash=_text_hash(content),
        input_tokens=_optional_int(usage.get("prompt_tokens")),
        output_tokens=_optional_int(usage.get("completion_tokens")),
        reasoning_tokens=_optional_int(
            completion_details.get("reasoning_tokens")
            if isinstance(completion_details, dict)
            else None
        ),
        cached_input_tokens=_optional_int(
            prompt_details.get("cached_tokens")
            if isinstance(prompt_details, dict)
            else None
        ),
        attempts=attempts,
    )


def _decode_json_object(value: str) -> dict[str, Any]:
    text = value.strip().lstrip("\ufeff")
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    text = _first_json_object(text)
    text = _remove_trailing_commas(text)
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise TypeError("model output is not an object")
    return decoded


def _first_json_object(value: str) -> str:
    start = value.find("{")
    if start < 0:
        return value
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(value)):
        character = value[index]
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]
    return value[start:]


def _remove_trailing_commas(value: str) -> str:
    output: list[str] = []
    quoted = False
    escaped = False
    index = 0
    while index < len(value):
        character = value[index]
        if quoted:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            index += 1
            continue
        if character == '"':
            quoted = True
        if character == ",":
            lookahead = index + 1
            while lookahead < len(value) and value[lookahead].isspace():
                lookahead += 1
            if lookahead < len(value) and value[lookahead] in "}]":
                index += 1
                continue
        output.append(character)
        index += 1
    return "".join(output)


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _elapsed_millis(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


_DETERMINISTIC_OPERATIONS = {
    "project_overview_source_selection",
    "project_overview_extraction",
    "technical_scoring_extraction",
    "consistency_review",
}

_QUALITY_OPERATIONS = {
    "bid_strategy_planning",
    "outline_skeleton_planning",
    "branch_blueprint_planning",
    "section_revision",
    "consistency_review",
}

_OPERATION_TEMPERATURES = {
    "bid_strategy_planning": 0.1,
    "outline_skeleton_planning": 0.15,
    "outline_branch_expansion": 0.2,
    "branch_blueprint_planning": 0.1,
    "chapter_drafting": 0.4,
    "section_revision": 0.2,
}

_OPERATION_MAX_TOKENS = {
    "project_overview_source_selection": 4096,
    "project_overview_extraction": 8192,
    "technical_scoring_extraction": 8192,
    "outline_branch_expansion": 8192,
    "outline_skeleton_planning": 16384,
}


def _operation_max_tokens(
    operation: str, payload: dict[str, Any]
) -> int | None:
    del payload
    return _OPERATION_MAX_TOKENS.get(operation)


def _operation_thinking_budget(operation: str, configured: int) -> int:
    limits = {
        "bid_strategy_planning": 3072,
        "outline_skeleton_planning": 1024,
        "branch_blueprint_planning": 3072,
        "section_revision": 2048,
    }
    return min(configured, limits.get(operation, configured))


def _payload_int(payload: dict[str, Any], key: str) -> int:
    value = _payload_value(payload, key)
    if not isinstance(value, int | str):
        return 1024
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1024


def _payload_value(payload: dict[str, Any], key: str) -> object:
    if key in payload:
        return payload[key]
    original = payload.get("originalInput")
    return original.get(key) if isinstance(original, dict) else None


def _operation_temperature(operation: str) -> float:
    if operation in _DETERMINISTIC_OPERATIONS:
        return 0
    return _OPERATION_TEMPERATURES.get(operation, 0.2)


def _operation_prompt(operation: str) -> str:
    shared = (
        "你是专业的技术投标文件编制专家。仅处理技术标内容，严格依据输入证据，"
        "不得编造商务条款、主体身份或无法追溯的参数。只输出满足 outputJsonSchema 的 JSON 对象，"
        "不要输出 Markdown 代码围栏或解释。"
    )
    instructions = {
        "project_overview_source_selection": (
            "通读input.segments中的完整招标文件，每个片段都有唯一id。只返回orderedSegmentIds。"
            "选择直接描述项目概述或项目内容的源片段，包括项目名称与编号、背景目标、采购或建设范围、"
            "技术内容与参数、实施边界、交付成果、工期进度、验收、培训、运维服务等。排除目录、重复"
            "页眉页脚、投标程序、资格条件、商务报价、评分办法、废标条款和格式装订要求。相同内容仅选"
            "信息最完整的一处，连续表格需保留必要的相邻片段。按信息重要性返回10至120个最有信息量的"
            "id，确有必要时可少于10个或增加到160个，但160是绝对上限；不得返回不存在的id，不得返回"
            "任何正文或解释。"
            "若input.window存在，说明招标文件过长、已按原文顺序切成input.window.total段，"
            "本次只给出其中第input.window.index段：只从本段片段中选择；本段若全是目录、程序、"
            "资格、商务、评分或格式内容，返回空数组，不要为凑数硬选。"
        ),
        "project_overview_extraction": (
            "input.selectedSegments是从完整招标文件中筛选出的项目概述源证据。只返回sections数组，"
            "根据原文实际结构整理3至8个内容区块，不要假定项目属于软件、工程、设备或服务中的任何"
            "一种。每个区块只包含title和content，title不得带Markdown井号，单个content通常不超过"
            "1500个字符，所有content合计不得超过6000个字符。"
            "区块应完整覆盖原文存在的项目名称与编号、背景目标、采购或建设范围、技术内容与参数、"
            "实施要求、交付成果、工期、验收、培训运维等项目内容；不存在的类别不得虚构。保持名称、"
            "数量、参数、期限和服务要求准确，避免重复。content可使用Markdown列表或表格。不得编写"
            "投标响应方案，不得输出评分办法、商务评分、资格条件、废标条款、格式装订要求或其他字段。"
        ),
        "technical_scoring_extraction": (
            "核对 input.clauseCatalog。clauseCatalog 是系统从技术"
            "评分窗口确定性建立的源条款目录，每条包含唯一 id、原始顺序、评分标题、分值和原文。只返回"
            "orderedClauseIds 一个字段：必须包含 clauseCatalog 中每个 id 恰好一次，并严格保持 order 顺序。"
            "不得返回、概括、改写或补充任何评分正文、标题、分值、解释或其他字段。该 ID 契约用于让系统"
            "直接使用招标文件原文组装技术部分评分要求，避免模型改写分值和证明材料。"
        ),
        "outline_skeleton_planning": (
            "以人工确认后的项目概述、技术评分要求和可选标书大纲为依据，只生成技术标一级、二级目录"
            "骨架，不得生成三级节点。outlineReferences只参考组织方式和命名风格，不得照搬项目事实。"
            "一级plannedPages之和等于targetPages，二级plannedPages必须为0。每个一级至少有2个二级，"
            "但2个只是兜底下限，通常应有3至6个。"
            "outlineScale.targetLevelTwoChapters是建议区间，应优先按独立技术对象和业务责任划分；"
            "输入事实不支持时可少于建议数量，不得为满足数量创建空泛或同义重复目录。"
            "系统会根据有效二级骨架自适应分配每个二级2至5个三级目录。必要时应把不同技术域、建设对象、实施阶段、"
            "保障体系和交付成果拆成不同一级或二级章节。每个二级节点必须填写具体taskBrief和"
            "mustKeywords，使后续模型仅凭该任务简述也能展开不重复的三级主题。不得使用空泛章节凑数。"
        ),
        "outline_branch_expansion": (
            "根据人工确认的项目概述、技术评分要求和branches中的一级、二级目录上下文，只返回三级"
            "目录明细。必须为每个parentKey精确生成preferredLeafCount个节点，节点的parentKey原样返回。"
            "每个标题对应一个独立建设对象、功能模块、实施步骤、控制措施、交付物或证明要求，并填写"
            "可直接指导正文写作的taskBrief和mustKeywords。相邻节点不得同义重复，不得生成一级、二级"
            "标题，不得使用‘总体方案’‘详细响应’‘配套措施’‘补充方案’等空泛标题凑数量。"
        ),
        "chapter_drafting": (
            "按writingPlan定义的语义职责续写章节，遵守写作总纲、风格画像、术语、承诺和上下文。"
            "先在内部规划各段的评审作用，再直接输出正文，不得输出规划过程。正文应充分、连贯，"
            "content 字段只返回可直接进入编辑器的受限HTML正文，不返回blocks、术语表或承诺表。"
            "当前目录标题由平台统一呈现，content中不得重复目录标题，不得输出h1至h6标题标签。"
            "正文内部如需分点，只允许使用‘1.’和‘（1）’两级阿拉伯数字序号，不得使用"
            "‘一、’‘（一）’‘第一章’等中文序号或章节式小标题。"
            "每个编号项必须使用独立p段落，不得把多个‘1.’或‘（1）’编号项连续写在同一个p中。"
            "使用‘第一，’‘第二，’‘第三，’等顺序词列举时，每一项也必须使用独立p段落。"
            "可按需要输出原生table表格，但不得使用Markdown管道表格，不得生成流程图、节点图或连线图。"
            "每张表必须严格输出三段结构：先输出非空的<p data-table-title=\"true\">语义表题</p>，"
            "再输出table，最后输出<p data-table-note=\"true\">表注</p>；表注允许为空。"
            "不得使用caption标签，表题不得写入th或td，表头和各数据行列数必须一致。正文不得出现"
            "‘对应段落’‘本段响应’等编制过程说明；确需呈现追踪关系时，只能写"
            "‘对应要求：’并紧跟具体招标要求。"
            "templateReferences 是其他项目标书范文的局部片段，只能参考结构、表达、深度和表格形式；"
            "不得复制其中的项目名称、主体、人员、案例、资质、金额、日期、参数或承诺。当前项目事实"
            "只能依据 criteria、dictionary、writingBible 和 commitmentRegistry。"
            "每段应有实际技术信息，优先写工程判断、组成关系、执行动作、产物和验证方法；"
            "不要重复前文，不要以宣传口号、同义改写、固定开场或机械总结填充篇幅。"
            "previousProse用于衔接而非复述，repetitionAvoidance中的表达应主动避开。"
        ),
        "section_revision": (
            "只改写用户选区，content字段返回可直接替换选区的受限HTML，保护冻结事实和前后文衔接，"
            "不返回blocks或重复HTML字段，不生成流程图。不得输出‘对应段落’等"
            "编制过程说明；确需呈现追踪关系时使用‘对应要求：具体要求’。不得输出h1至h6标题标签；"
            "分点只允许使用‘1.’和‘（1）’，不得使用‘一、’‘（一）’‘第一章’等中文序号或章节式小标题。"
            "每个编号项必须使用独立p段落，不得把多个编号项合并在同一个p中。"
            "‘第一，’‘第二，’‘第三，’等顺序词列举也必须逐项使用独立p段落。"
            "需要表格时只输出原生HTML table，不得输出Markdown管道表格。每张表必须采用非空"
            "data-table-title段落、table、可空data-table-note段落的三段结构；不得使用caption标签，"
            "不得把表题写入th或td。"
            "当mode为POLISH或instruction要求风格编辑时，只能删除重复和空泛套话、拆分过长句、"
            "改善段落衔接及补足已有事实的动作表达；不得改变任何数字、主体、时限、参数、"
            "承诺、表格行列或技术结论，也不得新增源材料没有的事实。"
        ),
        "consistency_review": (
            "审查技术要求响应风险、暗标合规、术语、参数、承诺和章节一致性。"
            "评分要求响应不足、证明材料待补和主观覆盖风险只能作为人工复核警告，"
            "不得仅凭这些问题判定正文不可发布。"
            "进行跨章节网络安全审查时必须区分核心计算与数据区、前置接入区和互联网出口区；"
            "核心区物理隔离与隔离区外经前置代理受控访问互联网可以同时成立。"
            "只有正文明确让同一核心安全域直接连接互联网，或没有交代安全域与受控边界时，"
            "才可判定为阻断级矛盾，并应指定可修订的chapterId和明确的统一口径。"
            "若input.batch存在，说明标书较长、按章节分成input.batch.total批审查，本次是第"
            "input.batch.index批：只对input.chapters中给出正文的章节提出问题，chapterId必须"
            "来自input.chapters；input.chapterIndex列出全书各章的标题与摘要，用于判断跨章节"
            "一致性与评分点覆盖，不要对未给出正文的章节下结论。"
        ),
    }
    return shared + instructions.get(operation, "完成指定技术标任务。")
