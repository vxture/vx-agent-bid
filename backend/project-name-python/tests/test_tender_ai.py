# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-02
import asyncio
import json
from typing import Any

import pytest

from czghagent_ai.services.outline_strategy import (
    build_outline_scale,
    normalize_skeleton,
    normalize_skeleton_pages,
    skeleton_scale_warnings,
    skeleton_structure_errors,
)
from czghagent_ai.services.structured_output import AiStructuredOutputError
from czghagent_ai.services.tender_ai import (
    TenderAiService,
    blocks_to_html,
    normalize_editor_content,
    normalize_model_blocks,
    normalize_outline_tree,
)
from czghagent_ai.tender_models import (
    ChapterDraftRequest,
    ContentBlock,
    InterpretationRequest,
    OutlineAssemblyRequest,
    OutlineExpansionStageRequest,
    OutlineRequest,
    OutlineSkeletonResponse,
    OutlineSkeletonStageRequest,
)


def bid_strategy_response() -> dict[str, Any]:
    return {
        "projectArchetype": "综合技术平台建设",
        "solutionPositioning": "围绕建设范围形成可实施、可验证的分层技术方案。",
        "designPrinciples": ["需求可追溯", "架构边界清晰", "交付结果可验证"],
        "technicalThemes": [
            {
                "title": "平台技术架构",
                "objective": "建立模块边界和协同关系",
                "approach": "按接入、处理、服务和运维职责组织技术能力并定义接口边界。",
                "components": ["接入层", "服务层"],
                "controls": ["接口校验"],
                "verification": ["架构评审"],
            },
            {
                "title": "实施与验收",
                "objective": "形成可执行的建设和验证路径",
                "approach": "按阶段组织实施、测试、交付和验收，并保留过程证据。",
                "components": ["实施控制", "验收管理"],
                "controls": ["质量检查"],
                "verification": ["交付物核验"],
            },
        ],
        "scoringResponses": [
            {
                "requirement": "技术方案完整、合理、可行",
                "evaluatorIntent": "确认方案具备完整设计和落地能力",
                "responseElements": ["技术架构", "实施方法"],
                "evidencePlan": ["架构关系和验收矩阵"],
                "priority": 5,
            }
        ],
        "crossCuttingConstraints": ["冻结参数和承诺保持一致"],
        "assumptions": [],
        "prohibitedClaims": ["未提供的人员、案例和资质"],
    }


def branch_blueprint_response(chapter_id: str = "chapter") -> dict[str, Any]:
    return {
        "solutionPositioning": "以统一技术边界和可验证实施路径完成当前二级技术域响应。",
        "sharedDecisions": ["采用统一模块边界和接口契约"],
        "sharedConstraints": ["保持冻结术语和承诺一致"],
        "chapters": [{
            "chapterId": chapter_id,
            "objective": "完成当前三级章节的专业技术响应。",
            "technicalDecisions": ["按职责边界组织技术方案"],
            "implementationActions": ["配置技术组件", "校验接口结果"],
            "deliverables": ["技术设计说明"],
            "validationMethods": ["执行设计评审"],
            "presentation": "连续技术段落",
        }],
        "assumptions": [],
        "prohibitedClaims": [],
    }


class FakeTenderAiProvider:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[object],
    ) -> dict[str, Any]:
        del response_model
        self.calls.append((operation, payload, user))
        return self.responses[operation]


class EchoTechnicalScoringProvider(FakeTenderAiProvider):
    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[object],
    ) -> dict[str, Any]:
        del response_model
        self.calls.append((operation, payload, user))
        if operation == "technical_scoring_extraction":
            return {
                "orderedClauseIds": [
                    clause["id"] for clause in payload["clauseCatalog"]
                ]
            }
        return self.responses[operation]


class RepairingTechnicalScoringProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[object],
    ) -> dict[str, Any]:
        del response_model
        self.calls.append((operation, payload, user))
        catalog = payload.get("clauseCatalog")
        if catalog is None:
            catalog = payload["originalInput"]["clauseCatalog"]
        ids = [clause["id"] for clause in catalog]
        return {"orderedClauseIds": ids[:-1] if len(self.calls) == 1 else ids}


class AdaptiveOutlineProvider:
    def __init__(
        self,
        surplus_leaves_per_branch: int = 0,
        skeleton_branch_count: int | None = None,
        omit_last_branch_per_batch: bool = False,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any], str]] = []
        self.surplus_leaves_per_branch = surplus_leaves_per_branch
        self.skeleton_branch_count = skeleton_branch_count
        self.omit_last_branch_per_batch = omit_last_branch_per_batch

    async def run(
        self,
        operation: str,
        payload: dict[str, Any],
        user: str,
        response_model: type[object],
    ) -> dict[str, Any]:
        del response_model
        self.calls.append((operation, payload, user))
        if operation == "bid_strategy_planning":
            return bid_strategy_response()
        if operation == "outline_skeleton_planning":
            branch_count = self.skeleton_branch_count or payload["outlineScale"][
                "targetLevelTwoChapters"
            ]["min"]
            root_count = max(1, (branch_count + 5) // 6)
            base, remainder = divmod(branch_count, root_count)
            nodes: list[dict[str, Any]] = []
            for root_index in range(1, root_count + 1):
                root_key = f"root-{root_index}"
                nodes.append({
                    "nodeKey": root_key,
                    "parentKey": None,
                    "level": 1,
                    "title": f"技术方案{root_index}",
                    "plannedPages": 1,
                    "taskBrief": "",
                })
                root_branches = base + (1 if root_index <= remainder else 0)
                for branch_index in range(1, root_branches + 1):
                    nodes.append({
                        "nodeKey": f"{root_key}-branch-{branch_index}",
                        "parentKey": root_key,
                        "level": 2,
                        "title": f"建设任务{root_index}-{branch_index}",
                        "plannedPages": 0,
                        "taskBrief": "细化建设对象、实施方法和交付要求",
                    })
            return {"nodes": nodes, "warnings": []}
        if operation == "outline_branch_expansion":
            expanded_nodes: list[dict[str, Any]] = []
            for branch_index, branch in enumerate(payload["branches"]):
                if (
                    self.omit_last_branch_per_batch
                    and len(payload["branches"]) > 1
                    and branch_index == len(payload["branches"]) - 1
                ):
                    continue
                expanded_nodes.extend({
                    "parentKey": branch["parentKey"],
                    "title": f"{branch['title']}具体主题{index}",
                    "taskBrief": f"细化{branch['title']}的第{index}项技术响应",
                    "mustKeywords": [branch["title"]],
                    "scoringPointIds": ["SP-001"],
                } for index in range(
                    1,
                    branch["preferredLeafCount"]
                    + self.surplus_leaves_per_branch
                    + 1,
                ))
            return {"nodes": expanded_nodes, "warnings": []}
        raise AssertionError(f"unexpected operation: {operation}")


def test_outline_scale_tracks_target_pages_without_using_hard_minimum_as_goal() -> None:
    scale_80 = build_outline_scale(80, "", "")
    scale_300 = build_outline_scale(300, "", "")
    scale_500 = build_outline_scale(500, "", "")

    assert (scale_80.target_leaf_min, scale_80.target_leaf_ideal,
            scale_80.target_leaf_max) == (26, 31, 35)
    assert (scale_300.target_leaf_min, scale_300.target_leaf_ideal,
            scale_300.target_leaf_max) == (91, 107, 118)
    assert (scale_500.target_leaf_min, scale_500.target_leaf_ideal,
            scale_500.target_leaf_max) == (152, 179, 197)
    assert scale_80.phased and scale_300.phased and scale_500.phased
    assert (scale_80.target_level_two_min, scale_80.target_level_two_max) == (7, 10)


def test_skeleton_page_budgets_are_system_owned() -> None:
    raw: dict[str, Any] = {
        "nodes": [
            {"nodeKey": "root", "parentKey": None, "level": 1, "plannedPages": 0},
            {"nodeKey": "branch", "parentKey": "root", "level": 2, "plannedPages": 9},
        ]
    }

    normalize_skeleton_pages(raw)

    assert raw["nodes"][0]["plannedPages"] == 1
    assert raw["nodes"][1]["plannedPages"] == 0
    assert raw["warnings"]


def test_an_oversized_skeleton_is_kept_as_is_and_the_user_is_told() -> None:
    """超出上限的骨架不裁、不拒、不让模型重来：原样保留，并给出可操作的提示。

    这里曾经把「超额」的二级目录公平裁掉，裁不下去时整份目录直接失败——
    2026-09-30 一份 100 页的标书就这样失败，页面上什么目录都没有。
    """
    raw = AdaptiveOutlineProvider(skeleton_branch_count=40)
    scale = build_outline_scale(80, "", "")
    skeleton = asyncio.run(raw.run(
        "outline_skeleton_planning", {"outlineScale": scale.payload()}, "test", object
    ))

    normalize_skeleton(skeleton, scale)
    response = OutlineSkeletonResponse.model_validate(skeleton)

    assert sum(node.level == 2 for node in response.nodes) == 40, "模型的结构原样保留"
    assert skeleton_structure_errors(response) == []
    warnings = skeleton_scale_warnings(response, scale)
    assert any(f"多于按篇幅估算的上限{scale.level_two_cap}个" in item for item in warnings)
    assert any("可直接使用" in item for item in warnings)


def test_the_cap_the_model_is_told_is_the_cap_the_warning_uses() -> None:
    """提示词和提示必须是同一个数：此前告诉模型 29，校验却卡在 21。"""
    scale = build_outline_scale(100, "", "")
    at_cap = OutlineSkeletonResponse.model_validate({"nodes": [
        {"nodeKey": "r", "parentKey": None, "level": 1, "title": "一", "plannedPages": 100},
        *[
            {"nodeKey": f"b{i}", "parentKey": "r", "level": 2, "title": f"二{i}",
             "plannedPages": 0, "taskBrief": "简述"}
            for i in range(scale.level_two_cap)
        ],
    ]})
    over = OutlineSkeletonResponse.model_validate({
        "nodes": [*at_cap.model_dump(by_alias=True)["nodes"],
                  {"nodeKey": "extra", "parentKey": "r", "level": 2, "title": "多一个",
                   "plannedPages": 0, "taskBrief": "简述"}],
    })

    assert scale.payload()["maxLevelTwoChapters"] == scale.level_two_cap
    assert skeleton_scale_warnings(at_cap, scale) == []
    assert skeleton_scale_warnings(over, scale)


def test_chapter_draft_rejects_content_that_remains_too_short_after_repair() -> None:
    client = FakeTenderAiProvider(
        {"chapter_drafting": {"content": "<p>" + "a" * 200 + "</p>", "summary": "响应不足"}}
    )
    service = TenderAiService(client)
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "under-budget-chapter",
            "bidTitle": "测试技术标",
            "biddingMode": "BLIND",
            "chapter": {"id": "leaf-1", "title": "专项智能体", "plannedPages": 0},
            "branchBlueprint": branch_blueprint_response("leaf-1"),
            "criteria": [],
            "wordBudget": 777,
        }
    )

    with pytest.raises(AiStructuredOutputError, match="业务完整性校验"):
        asyncio.run(service.draft(request))

    assert [call[0] for call in client.calls] == [
        "chapter_drafting", "chapter_drafting"
    ]


def test_small_chapter_draft_accepts_644_characters_and_keeps_original_prompt_budget() -> None:
    client = FakeTenderAiProvider(
        {"chapter_drafting": {"content": "<p>" + "a" * 644 + "</p>", "summary": "完整响应"}}
    )
    service = TenderAiService(client)
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "small-chapter",
            "bidTitle": "测试技术标",
            "biddingMode": "BLIND",
            "chapter": {"id": "leaf-1", "title": "实施方法", "plannedPages": 0},
            "branchBlueprint": branch_blueprint_response("leaf-1"),
            "criteria": [],
            "wordBudget": 489,
        }
    )

    response = asyncio.run(service.draft(request))

    assert response.html == "<p>" + "a" * 644 + "</p>"
    prompt = json.dumps(client.calls[0][1], ensure_ascii=False)
    assert "建议正文可见字符为391至562字" in prompt


def test_chapter_draft_accepts_over_budget_content_without_corrective_retry() -> None:
    client = FakeTenderAiProvider(
        {"chapter_drafting": {"content": "<p>" + "a" * 1881 + "</p>", "summary": "完整响应"}}
    )
    service = TenderAiService(client)
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "marginal-over-budget-chapter",
            "bidTitle": "测试技术标",
            "biddingMode": "BLIND",
            "chapter": {"id": "leaf-1", "title": "实施方法", "plannedPages": 0},
            "branchBlueprint": branch_blueprint_response("leaf-1"),
            "criteria": [],
            "wordBudget": 1087,
        }
    )

    response = asyncio.run(service.draft(request))

    assert response.html == "<p>" + "a" * 1881 + "</p>"
    assert [call[0] for call in client.calls] == ["chapter_drafting"]


def test_chapter_draft_removes_trailing_encoded_space() -> None:
    client = FakeTenderAiProvider(
        {"chapter_drafting": {"content": "<p>" + "a" * 644 + "</p>&#x20;", "summary": "完整响应"}}
    )
    service = TenderAiService(client)
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "encoded-space-chapter",
            "bidTitle": "测试技术标",
            "biddingMode": "BLIND",
            "chapter": {"id": "leaf-1", "title": "实施方法", "plannedPages": 0},
            "branchBlueprint": branch_blueprint_response("leaf-1"),
            "criteria": [],
            "wordBudget": 489,
        }
    )

    response = asyncio.run(service.draft(request))

    assert response.html == "<p>" + "a" * 644 + "</p>"


def test_interpretation_returns_one_result_for_each_business_object() -> None:
    client = EchoTechnicalScoringProvider(
        {
            "project_overview_source_selection": {
                "orderedSegmentIds": ["segment-0001"],
            },
            "project_overview_extraction": {
                "sections": [
                    {"title": "项目概述", "content": "建设统一技术平台。"},
                ],
            },
        }
    )
    service = TenderAiService(client)
    result = asyncio.run(
        service.interpret(InterpretationRequest.model_validate(
            {
                "requestId": "req-1",
                "documentId": "doc-1",
                "title": "测试技术标",
                "biddingMode": "OPEN",
                "segments": [
                    {"locatorType": "PAGE", "locator": "第 1 页", "text": "项目内容"},
                    {"locatorType": "TABLE", "locator": "第 8 页表格", "text": "技术部分：20分"},
                    {"locatorType": "TABLE", "locator": "第 8 页表格", "text": "实施方案（20分）"},
                    {
                        "locatorType": "TABLE",
                        "locator": "第 8 页表格",
                        "text": "方案完整、可行得20分；方案基本完整得10分；无方案得0分。",
                    },
                    {"locatorType": "TABLE", "locator": "第 8 页表格", "text": "（2）商务评分"},
                ],
            })
        )
    )

    assert result.project_overview.startswith("## 项目概述")
    assert "20分" in result.technical_scoring_requirements
    assert "方案完整、可行得20分" in result.technical_scoring_requirements
    assert {call[0] for call in client.calls} == {
        "project_overview_source_selection",
        "project_overview_extraction",
        "technical_scoring_extraction",
    }
    assert len(client.calls) == 3
    scoring_call = next(call for call in client.calls if call[0] == "technical_scoring_extraction")
    assert "segments" not in scoring_call[1]
    assert any(
        "方案完整、可行得20分" in clause["text"]
        for clause in scoring_call[1]["clauseCatalog"]
    )
    overview_call = next(call for call in client.calls if call[0] == "project_overview_extraction")
    assert [item["id"] for item in overview_call[1]["selectedSegments"]] == [
        "segment-0001"
    ]
    assert overview_call[1]["selectedSegments"][0]["text"] == "项目内容"


def test_technical_scoring_merges_all_windows_and_excludes_commercial_sections() -> None:
    first_clause = "方案完整、措施可行得10分；内容不完整得5分；无方案得0分。"
    second_clause = "培训内容完整、计划清晰得5分；内容简略得2分；未提供不得分。"
    client = EchoTechnicalScoringProvider({})
    service = TenderAiService(client)
    request = InterpretationRequest.model_validate(
        {
            "requestId": "req-windows",
            "documentId": "doc-windows",
            "title": "多评分表测试",
            "biddingMode": "OPEN",
            "segments": [
                {"locatorType": "PAGE", "locator": "第1页", "text": "技术评分标准（第一部分）"},
                {"locatorType": "TABLE", "locator": "表1", "text": "实施方案（10分）"},
                {"locatorType": "TABLE", "locator": "表1", "text": first_clause},
                {"locatorType": "TABLE", "locator": "表1", "text": "商务评分标准"},
                {"locatorType": "TABLE", "locator": "表1", "text": "企业业绩完整得5分。"},
                {"locatorType": "PAGE", "locator": "第2页", "text": "技术评分标准（续）"},
                {"locatorType": "TABLE", "locator": "表2", "text": "培训方案（5分）"},
                {"locatorType": "TABLE", "locator": "表2", "text": second_clause},
                {"locatorType": "TABLE", "locator": "表2", "text": "报价评分标准"},
                {"locatorType": "TABLE", "locator": "表2", "text": "最低价得30分。"},
                {
                    "locatorType": "PAGE",
                    "locator": "第3页",
                    "text": "技术评分标准：见评标办法前附表",
                },
                {"locatorType": "PAGE", "locator": "第3页", "text": "综合得分=A+B+C。"},
            ],
        }
    )

    result = asyncio.run(service.extract_technical_scoring(request))

    assert first_clause in result.technical_scoring_requirements
    assert second_clause in result.technical_scoring_requirements
    submitted = [clause["text"] for clause in client.calls[0][1]["clauseCatalog"]]
    assert first_clause in submitted and second_clause in submitted
    assert all("商务" not in text and "报价" not in text for text in submitted)


def test_technical_scoring_retries_when_a_source_clause_is_missing() -> None:
    first_clause = "方案完整得6分；方案不完整得3分；未提供得0分。"
    second_clause = "保障措施完整可靠得4分；内容简略得2分；未提供不得分。"
    client = RepairingTechnicalScoringProvider()
    service = TenderAiService(client)
    request = InterpretationRequest.model_validate(
        {
            "requestId": "req-repair",
            "documentId": "doc-repair",
            "title": "完整性纠正测试",
            "biddingMode": "BLIND",
            "segments": [
                {"locatorType": "TABLE", "locator": "表1", "text": "技术评分标准"},
                {"locatorType": "TABLE", "locator": "表1", "text": "实施方案（6分）"},
                {"locatorType": "TABLE", "locator": "表1", "text": first_clause},
                {"locatorType": "TABLE", "locator": "表1", "text": "保障措施（4分）"},
                {"locatorType": "TABLE", "locator": "表1", "text": second_clause},
                {"locatorType": "TABLE", "locator": "表1", "text": "商务评分标准"},
            ],
        }
    )

    result = asyncio.run(service.extract_technical_scoring_result(request))

    assert result.attempts == 2
    assert second_clause in result.data.technical_scoring_requirements
    assert "validationErrors" in client.calls[1][1]
    assert any("缺少源条款ID" in error for error in client.calls[1][1]["validationErrors"])


def test_technical_scoring_uses_source_catalog_when_id_correction_still_fails() -> None:
    clause = "方案完整得6分；内容简略得3分；未提供得0分。"
    client = FakeTenderAiProvider({
        "technical_scoring_extraction": {"orderedClauseIds": ["unknown-id"]}
    })
    service = TenderAiService(client)
    request = InterpretationRequest.model_validate({
        "requestId": "req-source-fallback",
        "documentId": "doc-source-fallback",
        "title": "确定性降级测试",
        "biddingMode": "OPEN",
        "segments": [
            {"locatorType": "TABLE", "locator": "表1", "text": "技术评分标准"},
            {"locatorType": "TABLE", "locator": "表1", "text": "实施方案（6分）"},
            {"locatorType": "TABLE", "locator": "表1", "text": clause},
            {"locatorType": "TABLE", "locator": "表1", "text": "商务评分标准"},
        ],
    })

    result = asyncio.run(service.extract_technical_scoring_result(request))

    assert result.attempts == 2
    assert clause in result.data.technical_scoring_requirements
    assert len(client.calls) == 2
    assert all(call[0] == "technical_scoring_extraction" for call in client.calls)


def test_outline_top_level_pages_are_balanced_to_target() -> None:
    client = AdaptiveOutlineProvider()
    service = TenderAiService(client)
    result = asyncio.run(
        service.outline(OutlineRequest.model_validate(
            {
                "requestId": "req-2",
                "title": "测试技术标",
                "targetPages": 10,
                "biddingMode": "BLIND",
                "criteria": [
                    {
                        "id": "c1",
                        "type": "PROJECT_OVERVIEW",
                        "title": "项目概述",
                        "description": "建设统一技术平台",
                    }
                ],
            })
        )
    )

    assert sum(node.planned_pages for node in result.nodes if node.level == 1) == 10
    assert all(node.planned_pages == 0 for node in result.nodes if node.level > 1)
    assert result.nodes[-1].scoring_point_ids == ["SP-001"]
    assert result.coverage[0].node_keys
    assert result.warnings


def test_outline_payload_uses_only_outline_reference_materials() -> None:
    client = AdaptiveOutlineProvider()
    request = OutlineRequest.model_validate(
        {
            "requestId": "outline-material-routing",
            "title": "测试技术标",
            "targetPages": 20,
            "biddingMode": "OPEN",
            "criteria": [
                {
                    "id": "overview",
                    "type": "PROJECT_OVERVIEW",
                    "title": "项目概述",
                    "description": "建设技术平台",
                }
            ],
            "references": [
                {"id": "outline", "category": "OUTLINE", "name": "大纲", "summary": "大纲内容"},
                {"id": "template", "category": "TEMPLATE", "name": "范本", "summary": "范本内容"},
            ],
        }
    )

    asyncio.run(TenderAiService(client).outline(request))

    payload = next(call[1] for call in client.calls if call[0] == "outline_skeleton_planning")
    assert payload["outlineReferences"] == [{"name": "大纲", "content": "大纲内容"}]
    assert payload["outlineScale"] == {
        "minLevelTwoChildrenPerLevelOne": 2,
        "minLevelThreeChildrenPerLevelTwo": 2,
        "preferredLevelTwoChildrenPerLevelOne": {"min": 3, "max": 6},
        "preferredLevelThreeChildrenPerLevelTwo": {"min": 3, "max": 5},
        "targetLeafChapters": {"min": 12, "ideal": 12, "max": 14},
        "targetLevelTwoChapters": {"min": 3, "max": 4},
        "maxLevelTwoChapters": 6,
        "maxLeafChapters": 16,
        "generationMode": "PHASED_QUOTA",
    }
    assert "范本内容" not in json.dumps(payload, ensure_ascii=False)


def test_a_model_that_writes_more_than_planned_keeps_its_outline_with_a_warning() -> None:
    """模型多写了三级小节：保留、展示、提示，而不是裁掉或让整份目录失败。"""
    client = AdaptiveOutlineProvider(
        surplus_leaves_per_branch=3,
        skeleton_branch_count=40,
    )
    request = OutlineRequest.model_validate({
        "requestId": "outline-surplus-kept",
        "title": "80页技术标",
        "targetPages": 80,
        "biddingMode": "BLIND",
        "criteria": [{
            "id": "overview",
            "type": "PROJECT_OVERVIEW",
            "title": "项目概述",
            "description": "建设统一技术平台",
        }],
    })

    result = asyncio.run(TenderAiService(client).outline_result(request))

    leaves = [node for node in result.data.nodes if node.level == 3]
    branches = [node for node in result.data.nodes if node.level == 2]
    assert len(branches) == 40, "骨架不裁"
    expansion_calls = [call for call in client.calls if call[0] == "outline_branch_expansion"]
    planned = sum(
        branch["preferredLeafCount"] for call in expansion_calls for branch in call[1]["branches"]
    )
    assert len(leaves) == planned + 3 * 40, "多写的三级小节原样保留"
    assert any("目录偏细" in warning for warning in result.data.warnings)
    assert any("二级目录共40个" in warning for warning in result.data.warnings)
    assert not any("裁剪" in warning for warning in result.data.warnings)


def test_a_branch_the_model_left_empty_is_shown_and_named_not_filled_with_templates() -> None:
    """模型漏掉一个二级的三级小节：不再用「…建设内容」「…技术实现」之类的模板标题补齐。"""
    client = AdaptiveOutlineProvider(omit_last_branch_per_batch=True)
    request = OutlineRequest.model_validate({
        "requestId": "outline-empty-branch-shown",
        "title": "80页技术标",
        "targetPages": 80,
        "biddingMode": "BLIND",
        "criteria": [{
            "id": "overview",
            "type": "PROJECT_OVERVIEW",
            "title": "项目概述",
            "description": "建设统一技术平台",
        }],
    })

    result = asyncio.run(TenderAiService(client).outline_result(request))

    leaves = [node for node in result.data.nodes if node.level == 3]
    assert leaves
    assert not any(node.title.endswith(("建设内容", "技术实现", "实施与控制")) for node in leaves)
    assert any("已从目录中略去" in warning for warning in result.data.warnings)
    assert all(node.level != 2 or any(leaf.parent_key == node.node_key for leaf in leaves)
               for node in result.data.nodes), "留在目录里的二级都有三级小节"


def test_outline_adapts_leaf_target_to_a_smaller_valid_skeleton() -> None:
    client = AdaptiveOutlineProvider(skeleton_branch_count=30)
    scoring = "\n".join(
        f"## 评分项{i}\n技术方案满足要求得1分" for i in range(1, 30)
    )
    request = OutlineRequest.model_validate({
        "requestId": "outline-adaptive-capacity-regression",
        "title": "500页技术标",
        "targetPages": 500,
        "biddingMode": "BLIND",
        "criteria": [
            {
                "id": "overview",
                "type": "PROJECT_OVERVIEW",
                "title": "项目概述",
                "description": "建设统一技术平台",
            },
            {
                "id": "scoring",
                "type": "TECHNICAL_SCORING",
                "title": "技术评分",
                "description": scoring,
            },
        ],
    })

    result = asyncio.run(TenderAiService(client).outline_result(request))

    leaves = [node for node in result.data.nodes if node.level == 3]
    assert len(leaves) == 150
    # 500 页、评分项较多时按篇幅估算约 197 节（每节 2.8 页，含复杂度加成）。30 个二级最多
    # 展开 150 节，偏差约 24%，超出 ±20% 容差：保留目录，并提示「偏粗」与每节页数。
    # 计划随骨架调整本身不再单独提示（此前是「由 197 个调整为 150 个」）。
    assert any("三级小节共150个" in warning and "偏粗" in warning
               for warning in result.data.warnings)
    assert not any("调整为" in warning for warning in result.data.warnings)
    expansion_calls = [
        call for call in client.calls if call[0] == "outline_branch_expansion"
    ]
    assert sum(
        branch["preferredLeafCount"]
        for call in expansion_calls
        for branch in call[1]["branches"]
    ) == 150


def test_large_outline_uses_skeleton_and_batched_expansion() -> None:
    client = AdaptiveOutlineProvider()
    request = OutlineRequest.model_validate({
        "requestId": "outline-phased",
        "title": "300页技术标",
        "targetPages": 300,
        "biddingMode": "BLIND",
        "criteria": [{
            "id": "overview",
            "type": "PROJECT_OVERVIEW",
            "title": "项目概述",
            "description": "建设统一技术平台",
        }],
    })

    result = asyncio.run(TenderAiService(client).outline_result(request))

    leaves = [node for node in result.data.nodes if node.level == 3]
    assert len(leaves) == 107
    assert sum(node.planned_pages for node in result.data.nodes if node.level == 1) == 300
    assert [call[0] for call in client.calls].count("outline_skeleton_planning") == 1
    assert [call[0] for call in client.calls].count("outline_branch_expansion") == 4
    assert [call[0] for call in client.calls].count("bid_strategy_planning") == 1
    expansion_calls = [call for call in client.calls if call[0] == "outline_branch_expansion"]
    assert all("outlineReferences" not in call[1] for call in expansion_calls)


def test_outline_stages_can_run_and_assemble_independently() -> None:
    client = AdaptiveOutlineProvider()
    service = TenderAiService(client)
    request = OutlineRequest.model_validate({
        "requestId": "outline-stages",
        "title": "分阶段技术标",
        "targetPages": 20,
        "biddingMode": "BLIND",
        "criteria": [{
            "id": "overview",
            "type": "PROJECT_OVERVIEW",
            "title": "项目概述",
            "description": "建设统一技术平台",
        }],
    })

    strategy = asyncio.run(service.outline_strategy_result(request))
    skeleton = asyncio.run(service.outline_skeleton_result(
        OutlineSkeletonStageRequest(outline=request, strategy=strategy.data)
    ))
    expansions = [
        asyncio.run(service.outline_expansion_result(OutlineExpansionStageRequest(
            outline=request,
            strategy=strategy.data,
            batch_index=index,
            branches=batch,
        ))).data
        for index, batch in enumerate(skeleton.data.batches, 1)
    ]
    assembled = service.assemble_outline(OutlineAssemblyRequest(
        outline=request,
        skeleton=skeleton.data,
        expansions=expansions,
    ))

    assert len([node for node in assembled.nodes if node.level == 3]) == 12
    assert sum(node.planned_pages for node in assembled.nodes if node.level == 1) == 20
    assert [call[0] for call in client.calls].count("bid_strategy_planning") == 1
    assert [call[0] for call in client.calls].count("outline_skeleton_planning") == 1


def test_outline_normalizer_promotes_shallow_leaves_and_moves_coverage() -> None:
    raw: dict[str, Any] = {
        "nodes": [
            {
                "nodeKey": "n1",
                "parentKey": None,
                "level": 1,
                "title": "技术方案",
                "plannedPages": 7,
                "taskBrief": "逐项响应",
                "mustKeywords": ["验收"],
                "scoringPointIds": ["c1"],
            }
        ],
        "coverage": [{"scoringPointId": "c1", "nodeKeys": ["n1"]}],
        "warnings": [],
    }

    normalize_outline_tree(raw)

    assert len(raw["nodes"]) == 7
    assert raw["nodes"][0]["plannedPages"] == 7
    leaf = next(node for node in raw["nodes"] if node["nodeKey"] == "n1-detail")
    assert leaf["level"] == 3
    assert leaf["plannedPages"] == 0
    assert leaf["mustKeywords"] == ["验收"]
    assert leaf["scoringPointIds"] == []
    assert raw["coverage"] == []
    assert raw["warnings"]


def test_outline_normalizer_keeps_only_top_level_page_budgets() -> None:
    raw: dict[str, Any] = {
        "nodes": [
            {
                "nodeKey": "n1",
                "parentKey": None,
                "level": 1,
                "title": "技术方案",
                "plannedPages": 4,
            },
            {
                "nodeKey": "n2",
                "parentKey": "n1",
                "level": 2,
                "title": "实施方案",
                "plannedPages": 3,
            },
            {
                "nodeKey": "n3",
                "parentKey": "n2",
                "level": 3,
                "title": "实施方法",
                "plannedPages": 7,
            },
        ],
        "warnings": [],
    }

    normalize_outline_tree(raw)

    assert raw["nodes"][0]["plannedPages"] == 4
    assert all(node["plannedPages"] == 0 for node in raw["nodes"] if node["level"] > 1)
    assert raw["warnings"]


def test_outline_normalizer_orders_grouped_model_nodes_depth_first() -> None:
    raw: dict[str, Any] = {
        "nodes": [
            {"nodeKey": "r1", "parentKey": None, "level": 1, "title": "第一章", "plannedPages": 5},
            {"nodeKey": "s1", "parentKey": "r1", "level": 2, "title": "第一节", "plannedPages": 0},
            {"nodeKey": "r2", "parentKey": None, "level": 1, "title": "第二章", "plannedPages": 5},
            {"nodeKey": "s2", "parentKey": "r2", "level": 2, "title": "第二节", "plannedPages": 0},
            {"nodeKey": "l1", "parentKey": "s1", "level": 3, "title": "第一项", "plannedPages": 0},
            {"nodeKey": "l2", "parentKey": "s2", "level": 3, "title": "第二项", "plannedPages": 0},
        ],
        "warnings": [],
    }

    normalize_outline_tree(raw)

    keys = [node["nodeKey"] for node in raw["nodes"]]
    assert keys.index("r1") < keys.index("s1") < keys.index("l1") < keys.index("r2")
    assert keys.index("r2") < keys.index("s2") < keys.index("l2")
    children: dict[str, list[dict[str, Any]]] = {}
    for node in raw["nodes"]:
        if node["parentKey"] is not None:
            children.setdefault(node["parentKey"], []).append(node)
    assert all(
        len(children[node["nodeKey"]]) >= 2
        for node in raw["nodes"]
        if node["level"] in {1, 2}
    )
    assert raw["warnings"]


def test_editor_content_flattens_headings_and_normalizes_chinese_numbering() -> None:
    content = normalize_editor_content(
        "<h4>一、总体方法</h4><p>（一）执行步骤</p><p>1. 已合规内容</p>"
    )

    assert "<h" not in content
    assert "<p>1. 总体方法</p>" in content
    assert "<p>（1）执行步骤</p>" in content
    assert "<p>1. 已合规内容</p>" in content


def test_editor_content_converts_collapsed_markdown_table_to_native_html() -> None:
    content = normalize_editor_content(
        "<p>表1 高性能推算服务运维内容 | 运维层面 | 服务内容 | 响应要求 | "
        "|----------|----------|----------| | 硬件运维 | 设备状态监控 | 7×24小时现场响应 | "
        "| 系统运维 | 补丁管理 | 每月一次例行维护 |</p>"
    )

    assert '<p data-table-title="true">高性能推算服务运维内容</p>' in content
    assert "<table>" in content and "<th><p>运维层面</p></th>" in content
    assert "<td><p>硬件运维</p></td>" in content
    assert "|----------|" not in content


def test_editor_content_converts_native_caption_to_editable_table_bundle() -> None:
    source = (
        "<table><caption>高性能推算服务运维内容</caption>"
        "<thead><tr><th>运维层面</th><th>服务内容</th></tr></thead>"
        "<tbody><tr><td>硬件运维</td><td>状态监控</td></tr></tbody></table>"
    )

    content = normalize_editor_content(source)

    assert content.startswith(
        '<p data-table-title="true">高性能推算服务运维内容</p><table>'
    )
    assert "<caption" not in content
    assert content.endswith('<p data-table-note="true"></p>')
    assert normalize_editor_content(content) == content


def test_editor_content_extracts_title_from_extra_right_header_cell() -> None:
    content = normalize_editor_content(
        "<table><thead><tr><th>运维层面</th><th>服务内容</th>"
        "<th>高性能推算服务运维内容</th></tr></thead>"
        "<tbody><tr><td>硬件运维</td><td>状态监控</td></tr></tbody></table>"
    )

    assert '<p data-table-title="true">高性能推算服务运维内容</p>' in content
    assert content.count("<th>") == 2
    assert "<th>高性能推算服务运维内容</th>" not in content


def test_editor_content_adds_contextual_title_and_empty_note_when_missing() -> None:
    content = normalize_editor_content(
        "<table><thead><tr><th>角色</th><th>职责</th></tr></thead>"
        "<tbody><tr><td>负责人</td><td>统筹</td></tr></tbody></table>",
        "项目组织",
    )

    assert content.startswith('<p data-table-title="true">项目组织明细表</p>')
    assert content.endswith('<p data-table-note="true"></p>')


def test_editor_content_keeps_one_existing_title_without_adding_fallback() -> None:
    source = (
        "<p>下表列明验收要求。</p>"
        '<p data-table-title="true">验收测试内容与通过准则表</p>'
        "<table><thead><tr><th>测试类型</th><th>通过准则</th></tr></thead>"
        "<tbody><tr><td>功能测试</td><td>全部通过</td></tr></tbody></table>"
    )

    content = normalize_editor_content(source, "验收测试与评审")

    assert content.count('data-table-title="true"') == 1
    assert "验收测试内容与通过准则表" in content
    assert "验收测试与评审明细表" not in content


def test_editor_content_collapses_consecutive_legacy_table_titles() -> None:
    source = (
        '<p data-table-title="true">验收测试内容与通过准则表</p>'
        '<p data-table-title="true">验收测试与评审明细表</p>'
        "<table><thead><tr><th>测试类型</th><th>通过准则</th></tr></thead>"
        "<tbody><tr><td>功能测试</td><td>全部通过</td></tr></tbody></table>"
    )

    content = normalize_editor_content(source, "验收测试与评审")

    assert content.count('data-table-title="true"') == 1
    assert "验收测试内容与通过准则表" in content
    assert "验收测试与评审明细表" not in content


def test_editor_content_splits_multiple_numbered_items_into_paragraphs() -> None:
    content = normalize_editor_content(
        "<p>1. 宣传部智能体设计 （1）建设定位与总体思路 正文内容。"
        " （2）核心功能模块 1）宣传文稿智能生成 功能说明。"
        " 2）宣传内容合规校核 功能说明。 2. 组织部智能体设计 正文内容。</p>"
    )

    assert content.count("<p>") == 6
    assert "<p>1. 宣传部智能体设计</p>" in content
    assert "<p>（1）建设定位与总体思路 正文内容。</p>" in content
    assert "<p>（1）宣传文稿智能生成 功能说明。</p>" in content
    assert "<p>（2）宣传内容合规校核 功能说明。</p>" in content
    assert "<p>2. 组织部智能体设计 正文内容。</p>" in content


def test_editor_content_splits_chinese_ordinal_items_after_sentence_boundary() -> None:
    content = normalize_editor_content(
        "<p>本项目的建设目标明确而系统。第一，建设统一大模型平台底座。"
        " 第二，建立长效运营机制。 第三，编制五年建设规划。</p>"
    )

    assert content == (
        "<p>本项目的建设目标明确而系统。</p>"
        "<p>第一，建设统一大模型平台底座。</p>"
        "<p>第二，建立长效运营机制。</p>"
        "<p>第三，编制五年建设规划。</p>"
    )


def test_rich_blocks_render_native_table_title_and_note() -> None:
    rendered = blocks_to_html(
        [
            ContentBlock.model_validate(
                {
                    "type": "table",
                    "caption": "职责表",
                    "note": "注：职责可按项目阶段调整。",
                    "header": ["角色", "职责"],
                    "rows": [["负责人", "统筹"]],
                }
            ),
        ]
    )

    assert "<table" in rendered and "<th>" in rendered
    assert '<p data-table-title="true">职责表</p>' in rendered
    assert '<p data-table-note="true">注：职责可按项目阶段调整。</p>' in rendered
    assert "data-flow-diagram" not in rendered
    json.dumps(rendered, ensure_ascii=False)


def test_model_block_normalizer_accepts_known_nested_shapes_only() -> None:
    raw: dict[str, Any] = {
        "blocks": [
            {"type": "bulletList", "items": [{"text": "第一项", "sourceRefs": []}]},
            {
                "type": "table",
                "data": {
                    "caption": "职责",
                    "note": "注：动态调整。",
                    "headers": ["角色"],
                    "rows": [["负责人"]],
                },
            },
            {"type": "flowchart", "title": "旧流程图"},
        ]
    }

    normalize_model_blocks(raw)

    assert raw["blocks"][0]["items"] == ["第一项"]
    assert raw["blocks"][1]["header"] == ["角色"]
    assert raw["blocks"][1]["note"] == "注：动态调整。"
    assert len(raw["blocks"]) == 2


def test_chapter_draft_payload_hides_internal_identifiers_and_status_fields() -> None:
    internal_id = "85f1f06b-2295-4bc0-8889-87a7e15d18da"
    client = FakeTenderAiProvider(
        {
            "chapter_drafting": {
                "content": "<p>" + "采用冻结后的技术口径并执行接口校验。" * 50 + "</p>",
                "summary": "技术口径已响应",
            }
        }
    )
    service = TenderAiService(client)
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "internal-request-id",
            "bidTitle": "测试技术标",
            "biddingMode": "BLIND",
            "chapter": {
                "id": internal_id,
                "title": "实施方案",
                "plannedPages": 5,
                "scoringPointIds": [internal_id],
            },
            "branchBlueprint": branch_blueprint_response(internal_id),
            "criteria": [
                {
                    "id": internal_id,
                        "type": "TECHNICAL_SCORING",
                        "title": "技术部分评分要求",
                        "description": "技术方案完整可行得20分",
                }
            ],
            "wordBudget": 1000,
        }
    )

    asyncio.run(service.draft(request))

    payload = next(call[1] for call in client.calls if call[0] == "chapter_drafting")
    serialized = json.dumps(payload, ensure_ascii=False)
    assert internal_id not in serialized
    assert "internal-request-id" not in serialized
    assert "biddingMode" not in serialized
    assert "scoringPointIds" not in serialized
    assert "暗标要求匿名编写" in serialized
    assert "建议正文可见字符为800至1150字" in serialized
    assert "不得为贴近字数重复背景、结论或同义表述" in serialized
    assert 'data-table-title=\\"true\\"' in serialized
    assert 'data-table-note=\\"true\\"' in serialized
    assert "表题只能放在table外部上方" in serialized
    assert "branchBlueprint" in payload


def test_chapter_draft_payload_includes_term_registry_and_omits_empty_source_excerpt() -> None:
    client = FakeTenderAiProvider(
        {
            "chapter_drafting": {
                "content": "<p>" + "按冻结边界执行技术响应和结果校验。" * 6 + "</p>",
                "summary": "技术响应",
            }
        }
    )
    service = TenderAiService(client)
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "draft-context",
            "bidTitle": "测试技术标",
            "biddingMode": "OPEN",
            "chapter": {"id": "chapter", "title": "算力方案", "plannedPages": 0},
            "branchBlueprint": branch_blueprint_response(),
            "criteria": [
                {
                    "id": "criterion",
                    "type": "TECHNICAL_SCORING",
                    "title": "算力评分要求",
                    "description": "提供物理隔离区域",
                    "sourceLocator": "评分表",
                    "sourceExcerpt": "",
                }
            ],
            "wordBudget": 100,
            "writingPlan": "先写技术判断，再写实施动作和验收产物",
            "styleProfile": "平均句长约32字，以技术动作表达为主",
            "previousProse": "<p>前文已完成建设边界说明。</p>",
            "chapterOpening": "<p>本节从算力资源调度展开。</p>",
            "recentTableCaption": "表3 算力资源清单",
            "repetitionAvoidance": ["本项目旨在", "通过上述措施"],
            "termRegistry": "与冻结字典重复的术语全文",
            "commitmentRegistry": "冻结承诺",
        }
    )

    asyncio.run(service.draft(request))

    payload = next(call[1] for call in client.calls if call[0] == "chapter_drafting")
    assert payload["termRegistry"] == "与冻结字典重复的术语全文"
    assert payload["commitmentRegistry"] == "冻结承诺"
    assert payload["writingPlan"].startswith("先写技术判断")
    assert payload["styleProfile"].startswith("平均句长")
    assert payload["previousProse"].startswith("<p>前文")
    assert payload["chapterOpening"].startswith("<p>本节")
    assert payload["recentTableCaption"] == "表3 算力资源清单"
    assert payload["repetitionAvoidance"] == ["本项目旨在", "通过上述措施"]
    assert "sourceExcerpt" not in payload["criteria"][0]
    assert payload["criteria"][0]["description"] == "提供物理隔离区域"


def test_chapter_draft_payload_uses_only_template_reference_segments() -> None:
    client = FakeTenderAiProvider(
        {"chapter_drafting": {
            "content": "<p>" + "按模板组织技术动作和验收结果。" * 6 + "</p>",
            "summary": "正文",
        }}
    )
    request = ChapterDraftRequest.model_validate(
        {
            "requestId": "draft-material-routing",
            "bidTitle": "测试技术标",
            "biddingMode": "OPEN",
            "chapter": {"id": "chapter", "title": "实施方案", "plannedPages": 0},
            "branchBlueprint": branch_blueprint_response(),
            "criteria": [],
            "evidence": [
                {"locatorType": "TEMPLATE_REFERENCE", "locator": "范本 / 实施", "text": "范本片段"},
                {"locatorType": "OUTLINE_REFERENCE", "locator": "大纲 / 实施", "text": "大纲片段"},
                {"locatorType": "PAGE", "locator": "招标文件第1页", "text": "源文件片段"},
            ],
            "wordBudget": 100,
        }
    )

    asyncio.run(TenderAiService(client).draft(request))

    payload = next(call[1] for call in client.calls if call[0] == "chapter_drafting")
    assert payload["templateReferences"] == [
        {
            "name": "范本 / 实施",
            "content": "范本片段",
            "purpose": "仅供本节同类内容的组织、专业密度和表格形式参考，不复制项目事实",
        }
    ]
    assert "大纲片段" not in json.dumps(payload, ensure_ascii=False)
