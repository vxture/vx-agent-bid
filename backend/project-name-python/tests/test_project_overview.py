# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-11
import asyncio
from typing import Any

import pytest

from czghagent_ai.services import project_overview
from czghagent_ai.services.project_overview import (
    ProjectOverviewExtractor,
    _clip_text,
    _evenly_cap,
    _normalize_draft,
    _render_markdown,
)
from czghagent_ai.services.structured_output import AiStructuredExecutor, AiStructuredOutputError
from czghagent_ai.tender_models import InterpretationRequest, ProjectOverviewDraft


class ProjectOverviewProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[object],
    ) -> dict[str, Any]:
        del user, response_model
        self.calls.append((operation, payload))
        if operation == "project_overview_source_selection":
            return {
                "orderedSegmentIds": [
                    "segment-0003",
                    "unknown",
                    "segment-0001",
                    "segment-0003",
                ]
            }
        return {
            "sections": [
                {"title": "## 项目名称及目标", "content": "建设统一技术平台。"},
                {"title": "交付与验收", "content": "完成部署并通过验收。"},
            ]
        }


def test_overview_selects_and_orders_evidence_before_composition() -> None:
    provider = ProjectOverviewProvider()
    extractor = ProjectOverviewExtractor(AiStructuredExecutor(provider))
    request = InterpretationRequest.model_validate({
        "requestId": "overview-test",
        "documentId": "doc-1",
        "title": "测试项目",
        "biddingMode": "OPEN",
        "segments": [
            {"locatorType": "PAGE", "locator": "第1页", "text": "项目名称"},
            {"locatorType": "PAGE", "locator": "第2页", "text": "投标程序"},
            {"locatorType": "TABLE", "locator": "第3页", "text": "验收要求"},
        ],
    })

    result = asyncio.run(extractor.extract(request))

    assert result.data.project_overview == (
        "## 项目名称及目标\n\n建设统一技术平台。\n\n"
        "## 交付与验收\n\n完成部署并通过验收。"
    )
    composition = provider.calls[1][1]
    assert [item["id"] for item in composition["selectedSegments"]] == [
        "segment-0001",
        "segment-0003",
    ]
    assert result.attempts == 2


def test_overview_schema_keeps_rendered_markdown_under_api_limit() -> None:
    class MaximumProvider(ProjectOverviewProvider):
        async def run(
            self,
            operation: str,
            payload: dict[str, Any],
            user: str,
            response_model: type[object],
        ) -> dict[str, Any]:
            del payload, user, response_model
            if operation == "project_overview_source_selection":
                return {"orderedSegmentIds": ["segment-0001"]}
            return {
                "sections": [
                    {"title": str(index) * 80, "content": "内" * 700}
                    for index in range(1, 9)
                ]
            }

    request = InterpretationRequest.model_validate({
        "requestId": "overview-max",
        "documentId": "doc-1",
        "title": "测试项目",
        "biddingMode": "OPEN",
        "segments": [
            {"locatorType": "PAGE", "locator": "第1页", "text": "项目内容"},
        ],
    })

    result = asyncio.run(
        ProjectOverviewExtractor(AiStructuredExecutor(MaximumProvider())).extract(request)
    )

    assert len(result.data.project_overview) <= 6500


def test_selected_source_clipping_preserves_both_ends() -> None:
    source = "A" * 500 + "B" * 500

    clipped = _clip_text(source, 220)

    assert clipped.startswith("A" * 90)
    assert clipped.endswith("B" * 90)
    assert "片段中部省略" in clipped
    assert len(clipped) <= 220


def test_oversized_model_selection_is_bounded_across_the_full_document() -> None:
    values = [f"segment-{index:04d}" for index in range(1, 686)]

    bounded = _evenly_cap(values, 160)

    assert len(bounded) == 160
    assert bounded[0] == "segment-0001"
    assert bounded[-1] == "segment-0685"
    assert any("0300" <= value[-4:] <= "0400" for value in bounded)


def test_overview_normalizer_bounds_total_markdown_instead_of_each_section() -> None:
    raw: dict[str, Any] = {
        "sections": [
            {"title": f"内容区块{index}", "content": "详细内容。" * 500}
            for index in range(1, 9)
        ]
    }

    _normalize_draft(raw)
    draft = ProjectOverviewDraft.model_validate(raw)

    assert len(_render_markdown(draft)) <= 6400
    assert len(draft.sections) == 8


# ── 分窗口选段 ─────────────────────────────────────────────────────────────
#
# 选段是唯一把整份招标文件送进模型的调用。2026-09-29 一份约 4 万字的文件撞上了
# Atlas 当时 100 KB 的请求体上限（联络函 40）；这一组盯的是：单次输入与文件长度脱钩，
# 而小文件的行为一字不变。



class _WindowedProvider:
    """每个窗口挑出其中含「项目」二字的片段；可让某些窗口答空，或越界答别的窗口的 id。"""

    def __init__(self, *, empty_windows: set[int] | None = None, poach: bool = False) -> None:
        self.selection_payloads: list[dict[str, Any]] = []
        self.composition: dict[str, Any] | None = None
        self._empty = empty_windows or set()
        self._poach = poach

    async def run(
        self, operation: str, payload: dict[str, Any], user: str, response_model: type[object]
    ) -> dict[str, Any]:
        del user, response_model
        if operation == "project_overview_source_selection":
            self.selection_payloads.append(payload)
            window = payload.get("window", {}).get("index", 1)
            if window in self._empty:
                return {"orderedSegmentIds": []}
            ids = [item["id"] for item in payload["segments"] if "项目" in item["text"]]
            if self._poach and window == 1:
                # segment-0399 在最后一个窗口里，且不含项目内容——只可能是越界答来的。
                ids.append("segment-0399")
            return {"orderedSegmentIds": ids}
        self.composition = payload
        return {"sections": [{"title": "项目", "content": "建设统一技术平台。"}]}


def _document(segment_count: int, characters: int = 1_000) -> InterpretationRequest:
    segments = [
        {
            "locatorType": "PAGE",
            "locator": f"第{index}页",
            "text": ("项目内容" if index % 10 == 0 else "投标程序") + "文" * characters,
        }
        for index in range(1, segment_count + 1)
    ]
    return InterpretationRequest.model_validate({
        "requestId": "windowed", "documentId": "doc-w", "title": "大文件",
        "biddingMode": "OPEN", "segments": segments,
    })


def _payload_characters(payload: dict[str, Any]) -> int:
    return sum(len(item["text"]) + len(item["locator"]) + 40 for item in payload["segments"])


def test_a_document_that_fits_is_still_one_call_without_a_window() -> None:
    provider = _WindowedProvider()

    asyncio.run(ProjectOverviewExtractor(AiStructuredExecutor(provider)).extract(_document(20)))

    assert len(provider.selection_payloads) == 1
    assert "window" not in provider.selection_payloads[0]


def test_every_selection_call_stays_under_the_window_budget_however_long_the_document() -> None:
    provider = _WindowedProvider()
    # 约 40 万字：十几页一个窗口，放在一次调用里是 1.2 MB 的请求体。
    request = _document(400)

    asyncio.run(ProjectOverviewExtractor(AiStructuredExecutor(provider)).extract(request))

    payloads = provider.selection_payloads
    assert len(payloads) > 1
    assert all(
        _payload_characters(payload) <= project_overview._SELECTION_WINDOW_CHARACTERS
        for payload in payloads
    )
    assert [payload["window"]["index"] for payload in payloads] == list(range(1, len(payloads) + 1))
    assert {payload["window"]["total"] for payload in payloads} == {len(payloads)}
    covered = [item["id"] for payload in payloads for item in payload["segments"]]
    assert covered == [f"segment-{index:04d}" for index in range(1, 401)], "不漏不重、保持原文顺序"


def test_window_answers_merge_in_document_order_and_empty_windows_are_fine() -> None:
    provider = _WindowedProvider(empty_windows={1})

    asyncio.run(ProjectOverviewExtractor(AiStructuredExecutor(provider)).extract(_document(400)))

    assert provider.composition is not None
    chosen = [item["id"] for item in provider.composition["selectedSegments"]]
    assert chosen == sorted(chosen), "按原文顺序"
    first_window = {item["id"] for item in provider.selection_payloads[0]["segments"]}
    assert not first_window & set(chosen), "答空的窗口不贡献片段"
    assert chosen, "其余窗口的项目片段都进了成文"


def test_a_window_cannot_answer_with_another_windows_segments() -> None:
    provider = _WindowedProvider(poach=True)

    asyncio.run(ProjectOverviewExtractor(AiStructuredExecutor(provider)).extract(_document(400)))

    assert provider.composition is not None
    chosen = [item["id"] for item in provider.composition["selectedSegments"]]
    assert "segment-0399" not in chosen


def test_no_project_content_in_any_window_fails_instead_of_writing_from_nothing() -> None:
    provider = _WindowedProvider(empty_windows=set(range(1, 100)))

    with pytest.raises(AiStructuredOutputError, match="未在招标文件中定位到项目内容"):
        asyncio.run(ProjectOverviewExtractor(AiStructuredExecutor(provider)).extract(_document(400)))

    assert provider.composition is None
