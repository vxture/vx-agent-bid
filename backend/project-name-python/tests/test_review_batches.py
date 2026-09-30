# GENERATED_BY_AI
# MODEL: claude-opus-5-5
# DATE: 2026-09-30
"""全文审查按章节分批：单次输入与标书规模脱钩，而合并不丢、不捏造问题。

审查把每章摘录（≤ 16,000 字）一起送入，200 页的标书约 0.6 MB、500 页约 1.5 MB，
而推理路由的窗口是 256K token（联络函 40、Atlas #69）。这一组盯的是：小标书一字不变；
大标书每批都在预算内、每批都看得见全书目录；合并时评分点「缺失」按全书判断。
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from czghagent_ai.services import tender_ai
from czghagent_ai.services.ai_provider import AiProviderDiagnostics
from czghagent_ai.services.structured_output import AiStructuredResult
from czghagent_ai.services.tender_ai import merge_reviews, review_batches
from czghagent_ai.tender_models import (
    ReviewCoverage,
    ReviewIssue,
    ReviewRequest,
    ReviewResponse,
)


def _payload(chapter_count: int, characters: int = 10_000) -> dict[str, Any]:
    return {
        "writingBible": {"tone": "正式"},
        "requirements": [{"id": "SP-001"}],
        "chapters": [
            {
                "chapterId": f"ch-{index}",
                "title": f"第{index}章",
                "summary": f"第{index}章摘要",
                "contentExcerpt": "正" * characters,
            }
            for index in range(1, chapter_count + 1)
        ],
    }


def _batches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], review_batches(payload, tender_ai._REVIEW_BATCH_CHARACTERS))


def _size(chapters: list[dict[str, Any]]) -> int:
    return sum(len(value) for chapter in chapters for value in chapter.values() if isinstance(value, str))


def test_a_bid_that_fits_is_reviewed_in_one_unchanged_call() -> None:
    payload = _payload(3)

    batches = _batches(payload)

    assert batches == [payload]


def test_every_batch_stays_under_budget_and_sees_the_whole_table_of_contents() -> None:
    payload = _payload(40)  # 约 40 万字：一次送入是 1.2 MB

    batches = _batches(payload)

    assert len(batches) > 1
    assert all(_size(batch["chapters"]) <= tender_ai._REVIEW_BATCH_CHARACTERS for batch in batches)
    reviewed = [chapter["chapterId"] for batch in batches for chapter in batch["chapters"]]
    assert reviewed == [f"ch-{index}" for index in range(1, 41)], "不漏不重、保持顺序"
    for number, batch in enumerate(batches, 1):
        assert batch["batch"] == {"index": number, "total": len(batches)}
        assert [item["chapterId"] for item in batch["chapterIndex"]] == [f"ch-{i}" for i in range(1, 41)]
        assert all("contentExcerpt" not in item for item in batch["chapterIndex"]), "目录不带正文"
        assert batch["writingBible"] == payload["writingBible"], "共享上下文每批都在"
        assert batch["requirements"] == payload["requirements"]


def test_an_oversized_chapter_gets_a_batch_of_its_own() -> None:
    payload = _payload(3, characters=10_000)
    payload["chapters"][1]["contentExcerpt"] = "长" * 70_000

    batches = _batches(payload)

    assert [[c["chapterId"] for c in batch["chapters"]] for batch in batches] == [["ch-1"], ["ch-2"], ["ch-3"]]


def _review(missing: list[str], *, passed: bool = True, issues: list[ReviewIssue] | None = None) -> ReviewResponse:
    return ReviewResponse(
        passed=passed,
        issues=issues or [],
        coverage=ReviewCoverage(total=3, covered=3 - len(missing), missing_scoring_point_ids=missing),
    )


def test_a_scoring_point_is_missing_only_if_no_batch_saw_it_covered() -> None:
    """某一批看不到覆盖它的章节，不等于全书没覆盖。"""
    merged = merge_reviews([_review(["SP-1", "SP-2"]), _review(["SP-2", "SP-3"])])

    assert merged.coverage.missing_scoring_point_ids == ["SP-2"]
    assert (merged.coverage.total, merged.coverage.covered) == (3, 2)


def test_issues_are_kept_from_every_batch_without_duplicates_and_one_failure_fails_all() -> None:
    issue = ReviewIssue(severity="ERROR", code="TERM", chapter_id="ch-1", message="术语不一致", suggestion="统一")
    other = ReviewIssue(severity="WARNING", code="DEPTH", chapter_id="ch-9", message="深度不足", suggestion="补充")

    merged = merge_reviews([_review([], issues=[issue]), _review([], passed=False, issues=[issue, other])])

    assert [item.chapter_id for item in merged.issues] == ["ch-1", "ch-9"]
    assert merged.passed is False


def test_a_long_bid_is_reviewed_batch_by_batch_and_merged() -> None:
    seen: list[dict[str, Any]] = []

    class Executor:
        async def execute_result(self, operation: str, payload: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            seen.append(payload)
            chapter = payload["chapters"][0]["chapterId"]
            issue = ReviewIssue(severity="WARNING", code="X", chapter_id=chapter, message=chapter, suggestion="-")
            return AiStructuredResult(
                ReviewResponse(passed=True, issues=[issue]),
                AiProviderDiagnostics(None, 1, "h", 10, 2, None, None, 1),
                1,
            )

    service = tender_ai.TenderAiService.__new__(tender_ai.TenderAiService)
    service._executor = Executor()  # type: ignore[assignment]

    result = asyncio.run(service.review_result(ReviewRequest(request_id="r", payload=_payload(40))))

    assert len(seen) > 1
    assert len(result.data.issues) == len(seen), "每一批的问题都在"
    assert result.attempts == len(seen)
