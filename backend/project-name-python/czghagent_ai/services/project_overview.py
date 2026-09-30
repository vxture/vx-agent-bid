# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-11
import asyncio
import hashlib
import re
from collections.abc import Callable
from typing import Any

from czghagent_ai.services.ai_provider import AiProviderDiagnostics
from czghagent_ai.services.structured_output import (
    AiStructuredExecutor,
    AiStructuredOutputError,
    AiStructuredResult,
)
from czghagent_ai.tender_models import (
    InterpretationRequest,
    ProjectOverviewDraft,
    ProjectOverviewResponse,
    ProjectOverviewSourceSelection,
    ProjectOverviewWindowSelection,
    SourceSegment,
)

_MAX_SELECTED_SOURCE_CHARACTERS = 48_000
_MAX_SELECTED_SEGMENTS = 160
_MAX_OVERVIEW_MARKDOWN_CHARACTERS = 6_400

#: 选段一次最多送入多少字符的招标原文。
#:
#: 选段是唯一一个把<b>整份招标文件</b>送进模型的调用，输入随文件页数无上限增长：
#: 2026-09-29 一份约 4 万字的文件就撞上了 Atlas 当时 100 KB 的请求体上限，
#: 三四百页的文件会撞上模型上下文窗口本身（联络函 40）。按窗口切开后，
#: 单次输入与文件长度脱钩。6 万字约合 3.5–4.5 万 token、约 180 KB：
#: 常见的招标文件仍是一次调用，行为与切窗口前完全相同；各路由的最小窗口是 128K token，
#: 留足了提示词、Schema 与输出的余量。
_SELECTION_WINDOW_CHARACTERS = 60_000

#: 同时在途的窗口数。窗口之间互不依赖，并行只缩短墙钟时间；上限防止一份超大文件
#: 一次把十几个请求同时压到同一条路由上。
_SELECTION_CONCURRENCY = 3


class ProjectOverviewExtractor:
    def __init__(self, executor: AiStructuredExecutor) -> None:
        self._executor = executor

    async def extract(
        self, request: InterpretationRequest
    ) -> AiStructuredResult[ProjectOverviewResponse]:
        """
        Select relevant evidence before composing a bounded project overview.

        Preconditions:
            - request.segments contains the ordered full-document extraction.
        Side Effects:
            - Calls the model for source selection and bounded composition.
        Error Semantics:
            - Structured output failures identify the failing bounded object.
        """
        indexed = _index_segments(request.segments)
        windows = _selection_windows(indexed, _SELECTION_WINDOW_CHARACTERS)
        if len(windows) == 1:
            selection = await self._executor.execute_result(
                "project_overview_source_selection",
                _selection_payload(request, indexed),
                f"{request.request_id}-overview-selection",
                ProjectOverviewSourceSelection,
                object_name="项目概述源片段选择",
                schema_version="project-overview-source-selection-v1",
                normalizer=_selection_normalizer(indexed),
            )
            selected_ids = selection.data.ordered_segment_ids
            selection_diagnostics = selection.diagnostics
            selection_attempts = selection.attempts
        else:
            selected_ids, selection_diagnostics, selection_attempts = (
                await self._select_by_window(request, indexed, windows)
            )
        selected = _selected_segments(indexed, selected_ids)
        draft = await self._executor.execute_result(
            "project_overview_extraction",
            _composition_payload(request, selected),
            f"{request.request_id}-overview-composition",
            ProjectOverviewDraft,
            object_name="项目概述",
            schema_version="interpretation-project-overview-v4",
            normalizer=_normalize_draft,
        )
        response = ProjectOverviewResponse(project_overview=_render_markdown(draft.data))
        return AiStructuredResult(
            data=response,
            diagnostics=merge_diagnostics(selection_diagnostics, draft.diagnostics),
            attempts=selection_attempts + draft.attempts,
        )

    async def _select_by_window(
        self,
        request: InterpretationRequest,
        indexed: list[tuple[str, SourceSegment]],
        windows: list[list[tuple[str, SourceSegment]]],
    ) -> tuple[list[str], AiProviderDiagnostics, int]:
        """逐窗口选段，再按原文顺序合并、封顶。

        每个窗口是一次独立的 ``project_overview_source_selection`` 调用，只看得见本窗口的片段，
        ``input.window`` 告诉模型它读的是第几段。窗口的答案可以为空。合并后按原文位置排序，
        再用与单窗口相同的均匀封顶收到 160 个——封顶在全文尺度上做，而不是每个窗口各取前几个，
        否则片段多的窗口与片段少的窗口会被同等对待。

        任一窗口失败即整体失败，不以「少一段也能写」降级：缺了哪一段，概述就缺哪一块项目内容，
        且看不出来。全部窗口都答空，同样按「没有定位到项目内容」失败。
        """
        gate = asyncio.Semaphore(_SELECTION_CONCURRENCY)
        total = len(windows)

        async def select(
            number: int, window: list[tuple[str, SourceSegment]]
        ) -> AiStructuredResult[ProjectOverviewWindowSelection]:
            async with gate:
                return await self._executor.execute_result(
                    "project_overview_source_selection",
                    _selection_payload(
                        request, window, window_index=number, window_total=total
                    ),
                    f"{request.request_id}-overview-selection-w{number}",
                    ProjectOverviewWindowSelection,
                    object_name=f"项目概述源片段选择（第{number}/{total}段）",
                    schema_version="project-overview-source-selection-v1",
                    normalizer=_selection_normalizer(window),
                )

        results = await asyncio.gather(
            *(select(number, window) for number, window in enumerate(windows, 1))
        )
        positions = {segment_id: index for index, (segment_id, _) in enumerate(indexed)}
        merged = sorted(
            {
                segment_id
                for result in results
                for segment_id in result.data.ordered_segment_ids
            },
            key=positions.__getitem__,
        )
        diagnostics = results[0].diagnostics
        for result in results[1:]:
            diagnostics = merge_diagnostics(diagnostics, result.diagnostics)
        attempts = sum(result.attempts for result in results)
        if not merged:
            raise AiStructuredOutputError(
                "项目概述未在招标文件中定位到项目内容",
                object_name="项目概述源片段选择",
                schema_version="project-overview-source-selection-v1",
                attempts=attempts,
                validation_errors=[f"{total} 个窗口均未返回项目内容片段"],
                finish_reason=diagnostics.finish_reason,
                response_length=diagnostics.response_length,
                response_hash=diagnostics.response_hash,
            )
        return _evenly_cap(merged, _MAX_SELECTED_SEGMENTS), diagnostics, attempts


def _index_segments(segments: list[SourceSegment]) -> list[tuple[str, SourceSegment]]:
    return [(f"segment-{index:04d}", segment) for index, segment in enumerate(segments, 1)]


def _selection_windows(
    indexed: list[tuple[str, SourceSegment]], budget: int
) -> list[list[tuple[str, SourceSegment]]]:
    """按原文顺序把片段切成若干窗口，每个窗口的字符量不超过 ``budget``。

    片段不跨窗口拆开：一个片段是解析器给出的最小定位单位，拆开后 id 与原文对不上。
    单个片段本身超过预算时独占一个窗口。计量口径与 ``_limit_segments`` 相同
    （正文 + 定位 + 每段 40 字符的 JSON 开销），而不是另起一套。
    """
    windows: list[list[tuple[str, SourceSegment]]] = [[]]
    size = 0
    for item in indexed:
        segment = item[1]
        segment_size = len(segment.text) + len(segment.locator) + 40
        if windows[-1] and size + segment_size > budget:
            windows.append([])
            size = 0
        windows[-1].append(item)
        size += segment_size
    return windows


def _selection_payload(
    request: InterpretationRequest,
    indexed: list[tuple[str, SourceSegment]],
    *,
    window_index: int | None = None,
    window_total: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "documentId": request.document_id,
        "title": request.title,
        "biddingMode": request.bidding_mode,
        "segments": [
            {"id": segment_id, **segment.model_dump(by_alias=True)}
            for segment_id, segment in indexed
        ],
    }
    if window_index is not None and window_total is not None:
        payload["window"] = {"index": window_index, "total": window_total}
    return payload


def _selection_normalizer(
    indexed: list[tuple[str, SourceSegment]],
) -> Callable[[dict[str, Any]], None]:
    positions = {segment_id: index for index, (segment_id, _) in enumerate(indexed)}

    def normalize(raw: dict[str, Any]) -> None:
        values = raw.get("orderedSegmentIds")
        if not isinstance(values, list):
            return
        valid = list(dict.fromkeys(
            value for value in values
            if isinstance(value, str) and value in positions
        ))
        bounded = _evenly_cap(valid, _MAX_SELECTED_SEGMENTS)
        raw["orderedSegmentIds"] = sorted(bounded, key=positions.__getitem__)

    return normalize


def _evenly_cap(values: list[str], limit: int) -> list[str]:
    if len(values) <= limit:
        return values
    if limit == 1:
        return values[:1]
    indexes = {
        round(index * (len(values) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [values[index] for index in sorted(indexes)]


def _selected_segments(
    indexed: list[tuple[str, SourceSegment]], selected_ids: list[str]
) -> list[dict[str, object]]:
    by_id = dict(indexed)
    selected = [(segment_id, by_id[segment_id]) for segment_id in selected_ids]
    per_segment_limit = max(200, _MAX_SELECTED_SOURCE_CHARACTERS // len(selected))
    return [
        {
            "id": segment_id,
            "locatorType": segment.locator_type,
            "locator": segment.locator,
            "text": _clip_text(segment.text, per_segment_limit),
        }
        for segment_id, segment in selected
    ]


def _clip_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    marker = "\n...[片段中部省略]...\n"
    side = max(1, (limit - len(marker)) // 2)
    return value[:side] + marker + value[-side:]


def _composition_payload(
    request: InterpretationRequest, selected: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "documentId": request.document_id,
        "title": request.title,
        "biddingMode": request.bidding_mode,
        "selectedSegments": selected,
    }


def _normalize_draft(raw: dict[str, Any]) -> None:
    sections = raw.get("sections")
    if not isinstance(sections, list):
        return
    normalized = [section for section in sections if isinstance(section, dict)][:8]
    for section in normalized:
        title = section.get("title")
        content = section.get("content")
        if isinstance(title, str):
            section["title"] = re.sub(r"^#{1,6}\s*", "", title.strip())[:80]
        if isinstance(content, str):
            section["content"] = content.strip()
    raw["sections"] = normalized
    _bound_rendered_content(normalized)


def _bound_rendered_content(sections: list[dict[str, Any]]) -> None:
    textual = [section for section in sections if isinstance(section.get("content"), str)]
    if not textual:
        return
    fixed_length = sum(
        5 + len(str(section.get("title", ""))) for section in textual
    ) + 2 * (len(textual) - 1)
    content_budget = max(len(textual), _MAX_OVERVIEW_MARKDOWN_CHARACTERS - fixed_length)
    lengths = [len(str(section["content"])) for section in textual]
    if sum(lengths) <= content_budget:
        return
    limits = _proportional_limits(lengths, content_budget)
    for section, limit in zip(textual, limits, strict=True):
        section["content"] = _truncate_markdown(str(section["content"]), limit)


def _proportional_limits(lengths: list[int], budget: int) -> list[int]:
    total = sum(lengths)
    limits = [max(1, length * budget // total) for length in lengths]
    while sum(limits) > budget:
        index = max(range(len(limits)), key=limits.__getitem__)
        limits[index] -= 1
    return limits


def _truncate_markdown(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    candidate = value[:limit].rstrip()
    minimum = limit // 2
    boundaries = [
        candidate.rfind(marker, minimum)
        for marker in ("\n\n", "\n", "。", "；")
    ]
    boundary = max(boundaries)
    if boundary < minimum:
        return candidate
    suffix = 1 if candidate[boundary] in "。；" else 0
    return candidate[: boundary + suffix].rstrip()


def _render_markdown(draft: ProjectOverviewDraft) -> str:
    sections: list[str] = []
    for section in draft.sections:
        title = re.sub(r"^#{1,6}\s*", "", section.title.strip())
        sections.append(f"## {title}\n\n{section.content.strip()}")
    return "\n\n".join(sections)


def merge_diagnostics(
    selection: AiProviderDiagnostics, composition: AiProviderDiagnostics
) -> AiProviderDiagnostics:
    return AiProviderDiagnostics(
        finish_reason=composition.finish_reason,
        response_length=selection.response_length + composition.response_length,
        response_hash=hashlib.sha256(
            f"{selection.response_hash}:{composition.response_hash}".encode("ascii")
        ).hexdigest(),
        input_tokens=_sum_optional(selection.input_tokens, composition.input_tokens),
        output_tokens=_sum_optional(selection.output_tokens, composition.output_tokens),
        reasoning_tokens=_sum_optional(
            selection.reasoning_tokens, composition.reasoning_tokens
        ),
        cached_input_tokens=_sum_optional(
            selection.cached_input_tokens, composition.cached_input_tokens
        ),
        attempts=selection.attempts + composition.attempts,
    )


def _sum_optional(first: int | None, second: int | None) -> int | None:
    if first is None and second is None:
        return None
    return (first or 0) + (second or 0)
