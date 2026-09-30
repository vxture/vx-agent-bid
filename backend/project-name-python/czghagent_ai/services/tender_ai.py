# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-02
import asyncio
import hashlib
import html
import json
import logging
import re
from typing import Any

from czghagent_ai.services.ai_provider import AiProviderDiagnostics, TenderAiProvider
from czghagent_ai.services.body_format import normalize_body_html, normalize_body_numbering_text
from czghagent_ai.services.outline_planner import AdaptiveOutlinePlanner
from czghagent_ai.services.project_overview import ProjectOverviewExtractor, merge_diagnostics
from czghagent_ai.services.structured_output import (
    AiStructuredExecutor,
    AiStructuredOutputError,
    AiStructuredResult,
)
from czghagent_ai.services.table_format import build_fallback_table_title
from czghagent_ai.services.technical_scoring import (
    build_technical_scoring_catalog,
    render_technical_scoring_markdown,
    selection_errors,
)
from czghagent_ai.strategy_models import BidStrategyResponse
from czghagent_ai.tender_models import (
    BranchBlueprint,
    BranchBlueprintRequest,
    ChapterContentResponse,
    ChapterDraftRequest,
    ChapterDraftResponse,
    ContentBlock,
    InterpretationRequest,
    InterpretationResponse,
    OutlineAssemblyRequest,
    OutlineExpansionResponse,
    OutlineExpansionStageRequest,
    OutlineRequest,
    OutlineResponse,
    OutlineSkeletonPlan,
    OutlineSkeletonStageRequest,
    ProjectOverviewResponse,
    ReviewCoverage,
    ReviewRequest,
    ReviewResponse,
    RevisionContentResponse,
    RevisionRequest,
    RevisionResponse,
    SourceSegment,
    TechnicalScoringResponse,
    TechnicalScoringSelectionResponse,
)

logger = logging.getLogger(__name__)


#: 装配阶段的占位诊断。
#:
#: 装配不调模型，所以没有 token、没有 finish_reason 可报。给一个显式的空值
#: 而不是复用某一批展开的诊断——后者会让「装配花了多少」看起来是个真实数字。
_ASSEMBLY_DIAGNOSTICS = AiProviderDiagnostics(
    finish_reason=None, response_length=0, response_hash="", 
    input_tokens=None, output_tokens=None,
)


class TenderAiService:
    _scoring_keywords = (
        "技术部分", "技术评分", "评分标准", "评审因素", "分值",
        "得分", "自主赋分",
    )

    def __init__(self, client: TenderAiProvider) -> None:
        self._client = client
        self._executor = AiStructuredExecutor(client)
        self._outline_planner = AdaptiveOutlinePlanner(self._executor)
        self._project_overview = ProjectOverviewExtractor(self._executor)

    async def interpret(self, request: InterpretationRequest) -> InterpretationResponse:
        overview, scoring = await asyncio.gather(
            self.extract_project_overview(request),
            self.extract_technical_scoring(request),
        )
        return InterpretationResponse(
            project_overview=overview.project_overview,
            technical_scoring_requirements=scoring.technical_scoring_requirements,
        )

    async def extract_project_overview(
        self, request: InterpretationRequest
    ) -> ProjectOverviewResponse:
        return (await self.extract_project_overview_result(request)).data

    async def extract_project_overview_result(
        self, request: InterpretationRequest
    ) -> AiStructuredResult[ProjectOverviewResponse]:
        return await self._project_overview.extract(request)

    async def extract_technical_scoring(
        self, request: InterpretationRequest
    ) -> TechnicalScoringResponse:
        return (await self.extract_technical_scoring_result(request)).data

    async def extract_technical_scoring_result(
        self, request: InterpretationRequest
    ) -> AiStructuredResult[TechnicalScoringResponse]:
        scoring_segments = self._technical_scoring_segments(request.segments)
        catalog = build_technical_scoring_catalog(scoring_segments)
        if not catalog.clauses:
            raise AiStructuredOutputError(
                "技术部分评分要求未定位到可组装的源评分条款",
                object_name="技术部分评分要求",
                schema_version="interpretation-technical-scoring-v4",
                attempts=1,
                validation_errors=["技术评分窗口内没有可识别的得分、赋分或分值档位条款"],
                finish_reason=None,
                response_length=0,
                response_hash=None,
            )
        # 只送条款目录，<b>不送整份招标文件</b>。
        #
        # 详细设计 §5.2：技术评分由确定性规则建立带稳定 ID 的原文条款目录，
        # 模型「只确认原文顺序」。目录里已经带着每条的原文，排序不需要别的东西。
        #
        # 两个都送有两处代价，而且都不报错：一是把整份招标文件重复塞进一次
        # 只需要排序的调用，白付一份输入 token；二是给了模型在目录之外「找」
        # 条款的材料，而这条路径的全部意义就是不让模型碰分值和证明材料。
        scoring_payload = {
            "documentId": request.document_id,
            "title": request.title,
            "biddingMode": request.bidding_mode,
            "clauseCatalog": catalog.to_prompt(),
        }
        try:
            selection = await self._executor.execute_result(
                "technical_scoring_extraction",
                scoring_payload,
                f"{request.request_id}-scoring",
                TechnicalScoringSelectionResponse,
                object_name="技术评分源条款选择",
                schema_version="interpretation-technical-scoring-v4",
                semantic_validator=lambda response: selection_errors(
                    response.ordered_clause_ids, catalog
                ),
            )
            return AiStructuredResult(
                TechnicalScoringResponse(
                    technical_scoring_requirements=render_technical_scoring_markdown(
                        catalog, selection.data.ordered_clause_ids
                    )
                ),
                selection.diagnostics,
                selection.attempts,
            )
        except AiStructuredOutputError as exception:
            logger.warning(
                "technical scoring ID selection failed; using source catalog fallback",
                extra={
                    "request_id": request.request_id,
                    "attempts": exception.attempts,
                    "response_hash": exception.response_hash,
                },
            )
            fallback_hash = exception.response_hash or hashlib.sha256(b"").hexdigest()
            return AiStructuredResult(
                TechnicalScoringResponse(
                    technical_scoring_requirements=render_technical_scoring_markdown(catalog)
                ),
                AiProviderDiagnostics(
                    finish_reason=exception.finish_reason,
                    response_length=exception.response_length,
                    response_hash=fallback_hash,
                    input_tokens=None,
                    output_tokens=None,
                ),
                exception.attempts,
            )

    def _technical_scoring_segments(
        self, segments: list[SourceSegment]
    ) -> list[SourceSegment]:
        score_pattern = re.compile(r"\d+(?:\.\d+)?\s*分")
        direct_anchors = [
            index for index, segment in enumerate(segments)
            if (
                (
                    ("技术评分" in segment.text or "技术评审" in segment.text)
                    and self._has_numeric_scoring_clause_nearby(segments, index)
                )
                or self._is_technical_table_marker(segments, index)
                or (
                    "实施方案" in segment.text
                    and score_pattern.search(segment.text)
                    and self._scoring_density(segments, index) > 0
                )
            )
        ]
        summary_anchors = [
            index for index, segment in enumerate(segments)
            if "技术部分" in segment.text and score_pattern.search(segment.text)
        ]
        anchors = direct_anchors or summary_anchors
        if not anchors:
            return self._select_segments(
                segments, self._scoring_keywords, before=4, after=20, max_characters=80_000
            )

        selected: set[int] = set()
        for anchor in anchors:
            start, end = self._technical_scoring_range(segments, anchor)
            if any(self._is_scoring_detail(segment.text) for segment in segments[start:end]):
                selected.update(range(start, end))
        if not selected:
            return self._select_segments(
                segments, self._scoring_keywords, before=4, after=20, max_characters=80_000
            )
        ordered = [segments[index] for index in sorted(selected)]
        return self._limit_segments(ordered, 80_000)

    def _has_numeric_scoring_clause_nearby(
        self, segments: list[SourceSegment], index: int
    ) -> bool:
        score_pattern = re.compile(r"\d+(?:\.\d+)?\s*分")
        return any(
            self._is_scoring_detail(segment.text) and score_pattern.search(segment.text)
            for segment in segments[index : index + 40]
        )

    def _is_technical_table_marker(
        self, segments: list[SourceSegment], index: int
    ) -> bool:
        text = segments[index].text.strip()
        marker = self._normalize_match_text(self._heading_core(text))
        if marker not in {"技术", "技术部分", "技术标"}:
            return False
        nearby = " ".join(segment.text for segment in segments[index : index + 3])
        return "评分标准" in nearby or "评审标准" in nearby

    def _technical_scoring_range(
        self, segments: list[SourceSegment], anchor: int
    ) -> tuple[int, int]:
        start = anchor
        end = min(len(segments), anchor + 240)
        has_scoring_detail = False
        for index in range(anchor + 1, end):
            has_scoring_detail = (
                has_scoring_detail or self._is_scoring_detail(segments[index].text)
            )
            if has_scoring_detail and self._is_non_technical_scoring_boundary(
                segments, index
            ):
                end = index
                while end > start and re.fullmatch(
                    r"\s*\d+(?:\.\d+){1,4}\s*", segments[end - 1].text
                ):
                    end -= 1
                return start, end
        return start, end

    def _is_non_technical_scoring_boundary(
        self, segments: list[SourceSegment], index: int
    ) -> bool:
        text = segments[index].text.strip()
        if not any(keyword in text for keyword in ("商务", "报价", "价格")):
            return False
        if re.search(r"(?:商务|报价|价格).{0,12}(?:评分|评审|标准)", text):
            return True
        nearby = " ".join(segment.text for segment in segments[index : index + 3])
        return len(text) <= 80 and bool(re.search(r"(?:评分|评审)标准", nearby))

    def _scoring_density(self, segments: list[SourceSegment], start: int) -> int:
        return sum(
            1 for segment in segments[start : start + 80]
            if self._is_scoring_detail(segment.text)
        )

    def _is_scoring_detail(self, text: str) -> bool:
        return bool(re.search(r"(?:得\s*\(?\d|得分|赋分|不计分|不得分)", text))

    def _heading_core(self, value: str) -> str:
        core = re.sub(
            r"[（(\[]?\s*\d+(?:\.\d+)?"
            r"(?:\s*[-–—~至]\s*\d+(?:\.\d+)?)?\s*分\s*[)）\]]?",
            "",
            value,
        )
        core = re.sub(r"^[\s（()）一二三四五六七八九十、.\d\-—]+", "", core)
        return core.strip()

    def _normalize_match_text(self, value: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]+", "", value).lower()

    def _select_segments(
        self,
        segments: list[SourceSegment],
        keywords: tuple[str, ...],
        before: int,
        after: int,
        max_characters: int,
    ) -> list[SourceSegment]:
        anchors = [
            index for index, segment in enumerate(segments)
            if any(keyword in segment.text for keyword in keywords)
        ]
        if not anchors:
            return self._limit_segments(segments, max_characters)
        selected: set[int] = set()
        size = 0
        for anchor in reversed(anchors):
            for index in range(
                max(0, anchor - before),
                min(len(segments), anchor + after + 1),
            ):
                if index in selected:
                    continue
                segment = segments[index]
                segment_size = len(segment.text) + len(segment.locator) + 40
                if size + segment_size <= max_characters:
                    selected.add(index)
                    size += segment_size
        return [segments[index] for index in sorted(selected)]

    def _limit_segments(
        self, segments: list[SourceSegment], max_characters: int
    ) -> list[SourceSegment]:
        selected: list[SourceSegment] = []
        size = 0
        for segment in segments:
            segment_size = len(segment.text) + len(segment.locator) + 40
            if selected and size + segment_size > max_characters:
                break
            selected.append(segment)
            size += segment_size
        return selected

    async def outline(self, request: OutlineRequest) -> OutlineResponse:
        return (await self.outline_result(request)).data

    async def outline_result(
        self, request: OutlineRequest
    ) -> AiStructuredResult[OutlineResponse]:
        return await self._outline_planner.plan_result(request)

    # ── 分阶段目录：与一次性路径共用同一批实现 ──────────────────────────────
    #
    # 存在的理由是可恢复：一次 500 页标书的三级展开有十几批，单批失败只该
    # 重跑那一批。这几个方法是 /internal/tender/outline/* 各路由的落点——
    # 它们曾经全部缺失，于是那些路由每次调用都是 AttributeError 变成的 500。

    async def outline_strategy_result(
        self, request: OutlineRequest
    ) -> AiStructuredResult[BidStrategyResponse]:
        return await self._outline_planner.plan_strategy_result(request)

    async def outline_skeleton_result(
        self, request: OutlineSkeletonStageRequest
    ) -> AiStructuredResult[OutlineSkeletonPlan]:
        return await self._outline_planner.plan_skeleton_result(
            request.outline, request.strategy
        )

    async def outline_expansion_result(
        self, request: OutlineExpansionStageRequest
    ) -> AiStructuredResult[OutlineExpansionResponse]:
        return await self._outline_planner.plan_expansion_result(
            request.outline, request.strategy, request.batch_index, request.branches
        )

    def assemble_outline(self, request: OutlineAssemblyRequest) -> OutlineResponse:
        """装配不调模型，所以<b>不是</b>协程，也不产生诊断。

        调用方可能是在重试之后才凑齐各批结果的，这一步必须是纯函数：
        同样的骨架和同样的批次结果，任何时候装出来的树都一样。
        """
        skeleton = AiStructuredResult(request.skeleton, _ASSEMBLY_DIAGNOSTICS, 0)
        expansions = [
            AiStructuredResult(item, _ASSEMBLY_DIAGNOSTICS, 0)
            for item in request.expansions
        ]
        return self._outline_planner.assemble(
            request.outline, skeleton, expansions
        ).data

    async def plan_branch_blueprint_result(
        self, request: BranchBlueprintRequest
    ) -> AiStructuredResult[BranchBlueprint]:
        """为一个二级分支规划技术域蓝图。

        它决定同一分支下各三级章节<strong>各写什么、不写什么</strong>。
        没有它，每一章都独立地把整个技术域讲一遍，相邻章节大面积重复，
        而每一章单独看都合理——这是最难在评审前发现的一类质量问题。
        """
        return await self._executor.execute_result(
            "branch_blueprint_planning",
            {
                "bidTitle": request.bid_title,
                "biddingMode": request.bidding_mode,
                "solutionContract": request.solution_contract,
                "branch": {
                    "title": request.branch.title,
                    "taskBrief": request.branch.task_brief,
                    "mustKeywords": request.branch.must_keywords,
                },
                # 章节 id 必须带上：蓝图要按 chapterId 回指到具体章节，
                # 而正文阶段再按它取出本章那一片（并在那里剥掉 id）。
                "chapters": [
                    {
                        "chapterId": chapter.id,
                        "title": chapter.title,
                        "taskBrief": chapter.task_brief,
                        "mustKeywords": chapter.must_keywords,
                    }
                    for chapter in request.chapters
                ],
                "criteria": [
                    {
                        "type": item.type,
                        "title": item.title,
                        "description": item.description,
                    }
                    for item in request.criteria
                ],
                "dictionary": request.dictionary.model_dump(by_alias=True),
                "writingBible": request.writing_bible,
                "termRegistry": request.term_registry,
                "commitmentRegistry": request.commitment_registry,
            },
            f"{request.request_id}-branch-blueprint",
            BranchBlueprint,
            object_name="二级技术域蓝图",
            schema_version="branch-blueprint-v1",
        )

    async def draft(self, request: ChapterDraftRequest) -> ChapterDraftResponse:
        return (await self.draft_result(request)).data

    async def draft_result(
        self, request: ChapterDraftRequest
    ) -> AiStructuredResult[ChapterDraftResponse]:
        result = await self._executor.execute_result(
            "chapter_drafting",
            self._draft_payload(request),
            f"{request.request_id}-draft",
            ChapterContentResponse,
            object_name="章节正文",
            schema_version="chapter-content-v3",
            normalizer=normalize_chapter_content_contract,
            semantic_validator=lambda response: chapter_completeness_errors(
                response.content, request.word_budget
            ),
        )
        content = result.data
        warnings = list(content.warnings)
        budget_warning = _chapter_budget_warning(content.content, request.word_budget)
        if budget_warning is not None and budget_warning not in warnings:
            warnings.append(budget_warning)
        response = ChapterDraftResponse(
            blocks=[],
            summary=content.summary or _content_summary(content.content),
            terms=[],
            commitments=[],
            warnings=warnings,
            html=normalize_editor_content(content.content, request.chapter.title),
        )
        return AiStructuredResult(response, result.diagnostics, result.attempts)

    def _draft_payload(self, request: ChapterDraftRequest) -> dict[str, Any]:
        minimum_characters = round(request.word_budget * 0.80)
        maximum_characters = round(request.word_budget * 1.15)
        writing_rules = [
            "正文只使用面向评审人员的自然语言，不输出接口字段名、对象ID或内部状态值",
            "平台已统一呈现当前三级目录标题；content中不得重复目录标题，不得使用h1至h6标题标签",
            "正文内部只有一个正文层级；需要分点时只允许使用‘1.’和‘（1）’两级阿拉伯数字序号",
            "不得使用‘一、’‘（一）’‘第一章’等中文序号或章节式段落小标题",
            "每个编号项必须放在独立p段落中，不得把多个编号项连续写在同一个p标签内",
            "使用‘第一，’‘第二，’‘第三，’等顺序词列举时，每一项也必须使用独立p段落",
            "不得生成流程图、节点图或连线图，可使用段落、列表和原生HTML表格表达",
            "不得输出Markdown管道表格；表格必须使用table、thead、tbody、tr、th、td标签",
            "不得出现‘对应段落’‘本段响应’等编制过程说明；确需呈现追踪关系时写‘对应要求：具体要求’",
            "每张表必须严格使用三段结构：非空的<p data-table-title=\"true\">语义表题</p>、"
            "原生<table>、紧随其后的<p data-table-note=\"true\">表注</p>；表注允许为空",
            "表题只能放在table外部上方，不得使用caption标签，不得把表题写入th或td单元格；"
            "表头和每行数据的列数必须一致",
            f"当前写作单元建议正文可见字符为{minimum_characters}至{maximum_characters}字；"
            "这是软目标，信息完整和表达紧凑优先，不得为贴近字数重复背景、结论或同义表述",
            "每个主要段落应提供新增技术信息，并尽量交代责任角色、输入、处理动作、输出成果、"
            "检查方法中的至少三项；源材料没有给出时不得虚构人员、数量、参数或时限",
            "直接写工程判断和实施做法，不使用‘随着信息技术的发展’‘具有重要意义’"
            "‘全面赋能’‘全面提升’‘形成完善闭环’等宣传性套话",
            "避免连续使用‘通过……实现……确保……’句式；允许自然使用长短句，"
            "不得为了句式变化替换已经冻结的专业术语",
            "除非承担必要的承上启下作用，不重复介绍项目背景、总体目标、建设原则，"
            "不在单元末尾机械增加‘综上所述’或成效总结",
        ]
        if request.bidding_mode == "BLIND":
            writing_rules.append("按暗标要求匿名编写，不出现投标人名称、标识、人员身份或暗示性信息")
        writing_rules.extend([
            "writingBible 和 commitmentRegistry 是全局不可改写约束，"
            "任何章节不得擅自改写工期、里程碑、服务时限和暗标称谓。",
            "如果本章涉及进度、售后、响应或运维，请优先沿用全局台账口径，只允许补充本章职责，不允许提高或放松承诺。",
            "templateReferences 仅用于参考章节组织、表达方式、内容深度和表格形式；"
            "不得复制其中的项目名称、招标人、投标人、人员、案例、资质、金额、日期、参数或承诺。",
            "当前项目的一切事实和承诺只能来自 criteria、dictionary、writingBible 和 commitmentRegistry。",
            "writingPlan 是当前单元的内部策划卡片，必须按其职责写作，但不得在正文中输出"
            "‘写作目标’‘段落职责’‘写作单元’等策划说明。",
            "previousProse 和 chapterOpening 只用于保持语气与衔接，不得逐句复述；"
            "repetitionAvoidance 中的开头和套话应主动避开。",
        ])
        criteria: list[dict[str, Any]] = []
        for item in request.criteria:
            criterion: dict[str, Any] = {
                "type": item.type,
                "title": item.title,
                "description": item.description,
                "sourceLocator": item.source_locator,
            }
            if item.score is not None:
                criterion["score"] = item.score
            if item.source_excerpt:
                criterion["sourceExcerpt"] = item.source_excerpt
            criteria.append(criterion)
        payload: dict[str, Any] = {
            "bidTitle": request.bid_title,
            "writingRules": writing_rules,
            "chapter": {
                "title": request.chapter.title,
                "taskBrief": request.chapter.task_brief,
                "mustKeywords": request.chapter.must_keywords,
            },
            "criteria": criteria,
            "dictionary": request.dictionary.model_dump(by_alias=True),
            "templateReferences": [
                {
                    "name": item.locator,
                    "content": item.text,
                    "purpose": "仅供本节同类内容的组织、专业密度和表格形式参考，不复制项目事实",
                }
                for item in request.evidence
                if item.locator_type == "TEMPLATE_REFERENCE"
            ],
            "writingPlan": request.writing_plan,
            "styleProfile": request.style_profile,
            "previousSummary": request.previous_summary,
            "previousProse": request.previous_prose,
            "chapterOpening": request.chapter_opening,
            "recentTableCaption": request.recent_table_caption,
            "repetitionAvoidance": request.repetition_avoidance,
            "nextBrief": request.next_brief,
            "wordBudget": request.word_budget,
            "unitIndex": request.unit_index,
            "unitCount": request.unit_count,
            "unitTitle": request.unit_title,
            "writingBible": request.writing_bible,
        }
        if request.commitment_registry:
            payload["commitmentRegistry"] = request.commitment_registry
        if request.term_registry:
            payload["termRegistry"] = request.term_registry
        blueprint = _branch_blueprint_prompt(request)
        if blueprint:
            # 分支蓝图是本章所在技术域的规划卡片。请求模型上一直有这个字段，
            # 调用方也一直在填，但它到这里就断了——填了等于没填，
            # 而没有任何迹象说明它被忽略了。
            payload["branchBlueprint"] = blueprint
        return payload

    async def revise(self, request: RevisionRequest) -> RevisionResponse:
        return (await self.revise_result(request)).data

    async def revise_result(
        self, request: RevisionRequest
    ) -> AiStructuredResult[RevisionResponse]:
        result = await self._executor.execute_result(
            "section_revision",
            request.model_dump(by_alias=True),
            f"{request.request_id}-revision",
            RevisionContentResponse,
            object_name="局部改写内容",
            schema_version="revision-content-v3",
            normalizer=normalize_revision_content_contract,
        )
        content = result.data
        rendered = normalize_editor_content(content.content)
        visible = re.sub(r"<[^>]+>", " ", rendered)
        preserved = [fact for fact in request.protected_facts if fact and fact in visible]
        missing = [fact for fact in request.protected_facts if fact and fact not in visible]
        warnings = [*content.warnings]
        if missing:
            warnings.append("部分保护事实未出现在候选内容中，请人工复核。")
        response = RevisionResponse(
            blocks=[],
            change_summary=content.change_summary or "已按要求调整选区内容",
            preserved_facts=preserved,
            warnings=warnings,
            html=rendered,
        )
        return AiStructuredResult(response, result.diagnostics, result.attempts)

    async def review(self, request: ReviewRequest) -> ReviewResponse:
        return (await self.review_result(request)).data

    async def review_result(
        self, request: ReviewRequest
    ) -> AiStructuredResult[ReviewResponse]:
        batches = review_batches(request.payload, _REVIEW_BATCH_CHARACTERS)
        if len(batches) == 1:
            return await self._executor.execute_result(
                "consistency_review",
                request.payload,
                f"{request.request_id}-review",
                ReviewResponse,
                object_name="成稿审查结果",
                schema_version="review-v2",
            )
        gate = asyncio.Semaphore(_REVIEW_CONCURRENCY)

        async def review_batch(
            number: int, payload: dict[str, object]
        ) -> AiStructuredResult[ReviewResponse]:
            async with gate:
                return await self._executor.execute_result(
                    "consistency_review",
                    payload,
                    f"{request.request_id}-review-b{number}",
                    ReviewResponse,
                    object_name=f"成稿审查结果（第{number}/{len(batches)}批）",
                    schema_version="review-v2",
                )

        results = await asyncio.gather(
            *(review_batch(number, payload) for number, payload in enumerate(batches, 1))
        )
        diagnostics = results[0].diagnostics
        for result in results[1:]:
            diagnostics = merge_diagnostics(diagnostics, result.diagnostics)
        return AiStructuredResult(
            merge_reviews([result.data for result in results]),
            diagnostics,
            sum(result.attempts for result in results),
        )

#: 一次审查最多送入多少字符的章节正文。
#:
#: 审查把每章摘录（≤ 16,000 字）一起送入，输入随标书规模线性增长：200 页的标书约 0.6 MB，
#: 500 页约 1.5 MB，而 ``chat/reasoning`` 的窗口是 256K token（联络函 40、Atlas #69）。
#: 超过这个量就按章节分批；常规规模的标书仍是一次调用，行为不变。
_REVIEW_BATCH_CHARACTERS = 60_000

#: 同时在途的审查批次。审查走推理路由，单次耗时长；并行只为缩短墙钟时间，不求压满路由。
_REVIEW_CONCURRENCY = 2


def _chapter_size(chapter: object) -> int:
    if not isinstance(chapter, dict):
        return 0
    return sum(len(value) for value in chapter.values() if isinstance(value, str))


def review_batches(payload: dict[str, object], budget: int) -> list[dict[str, object]]:
    """把审查请求按章节切成若干批；放得下时原样返回一个。

    每批带齐共享上下文（写作规范、术语与承诺登记、评分要求）与<b>全书目录</b>
    （每章 id、标题与已有的摘要），只把本批章节的正文放进 ``chapters``——跨章一致性
    靠目录与摘要判断，而正文级的问题只针对本批章节提出。章节不拆开，按原文顺序装批；
    单章超过预算时独占一批。
    """
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or sum(_chapter_size(item) for item in chapters) <= budget:
        return [payload]
    groups: list[list[object]] = [[]]
    size = 0
    for chapter in chapters:
        chapter_size = _chapter_size(chapter)
        if groups[-1] and size + chapter_size > budget:
            groups.append([])
            size = 0
        groups[-1].append(chapter)
        size += chapter_size
    index = [
        {
            key: chapter[key]
            for key in ("chapterId", "title", "summary")
            if key in chapter
        }
        for chapter in chapters
        if isinstance(chapter, dict)
    ]
    shared = {key: value for key, value in payload.items() if key != "chapters"}
    return [
        {
            **shared,
            "chapters": group,
            "chapterIndex": index,
            "batch": {"index": number, "total": len(groups)},
        }
        for number, group in enumerate(groups, 1)
    ]


def merge_reviews(reviews: list[ReviewResponse]) -> ReviewResponse:
    """合并分批审查的结论。

    问题逐条合并、按（严重度、码、章节、描述）去重。评分点覆盖在<b>全书</b>尺度上判断：
    某批看不到覆盖它的章节，不等于全书没覆盖——所以一个评分点只有在<b>每一批</b>都报缺失时
    才算缺失。任一批不通过即整体不通过。
    """
    seen: set[tuple[str, str, str, str]] = set()
    issues = []
    for review in reviews:
        for issue in review.issues:
            key = (issue.severity, issue.code, issue.chapter_id, issue.message)
            if key not in seen:
                seen.add(key)
                issues.append(issue)
    total = max((review.coverage.total for review in reviews), default=0)
    reporting = [review.coverage for review in reviews if review.coverage.total > 0]
    missing: list[str] = []
    if reporting:
        common = set(reporting[0].missing_scoring_point_ids)
        for coverage in reporting[1:]:
            common &= set(coverage.missing_scoring_point_ids)
        missing = [item for item in reporting[0].missing_scoring_point_ids if item in common]
    warnings = list(dict.fromkeys(item for review in reviews for item in review.warnings))
    summary = "；".join(review.review_summary for review in reviews if review.review_summary)
    return ReviewResponse(
        passed=all(review.passed for review in reviews),
        issues=issues,
        coverage=ReviewCoverage(total=total, covered=max(0, total - len(missing)),
                                missing_scoring_point_ids=missing),
        warnings=warnings,
        review_summary=summary[:3000],
    )


def blocks_to_html(blocks: list[ContentBlock]) -> str:
    output: list[str] = []
    for block in blocks:
        source_refs = html.escape(json.dumps(block.source_refs, ensure_ascii=False), quote=True)
        if block.type == "heading":
            text = html.escape(normalize_body_numbering_text(block.text))
            output.append(f'<p data-source-refs="{source_refs}">{text}</p>')
        elif block.type == "paragraph":
            output.append(f'<p data-source-refs="{source_refs}">{html.escape(block.text)}</p>')
        elif block.type in {"bulletList", "orderedList"}:
            tag = "ul" if block.type == "bulletList" else "ol"
            items = "".join(f"<li><p>{html.escape(item)}</p></li>" for item in block.items)
            output.append(f'<{tag} data-source-refs="{source_refs}">{items}</{tag}>')
        elif block.type == "table":
            caption = html.escape(
                block.caption.strip() or build_fallback_table_title(block.header)
            )
            note = html.escape(block.note)
            header = "".join(f"<th><p>{html.escape(cell)}</p></th>" for cell in block.header)
            rows = "".join(
                "<tr>" + "".join(f"<td><p>{html.escape(cell)}</p></td>" for cell in row) + "</tr>"
                for row in block.rows
            )
            output.append(
                f'<p data-table-title="true">{caption}</p>'
                f'<table data-source-refs="{source_refs}"><thead><tr>{header}</tr></thead>'
                f'<tbody>{rows}</tbody></table><p data-table-note="true">{note}</p>'
            )
    return "".join(output)


#: 首尾的空白，含<b>编码形式</b>的空白。
#:
#: ``strip()`` 只认字面空白，看不见 ``&#x20;`` 和 ``&nbsp;``。模型在结尾多吐一个
#: 编码空格，它会落在最后一个块元素<em>外面</em>——编辑器里是一个孤立的空段，
#: 导出的 DOCX 里是一个空行。不报错，只是每一份成果都比预期多一行。
_ENCLOSING_BLANKS = re.compile(
    r"^(?:\s|&nbsp;|&#(?:32|160|x20|xa0);)+|(?:\s|&nbsp;|&#(?:32|160|x20|xa0);)+$",
    flags=re.IGNORECASE,
)


def normalize_editor_content(value: str, fallback_table_context: str = "") -> str:
    content = _ENCLOSING_BLANKS.sub("", value)
    content = re.sub(r"```(?:html)?\s*|```", "", content, flags=re.IGNORECASE)
    content = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s+on[a-z]+\s*=\s*(['\"]).*?\1", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s+(?:href|src)\s*=\s*(['\"])javascript:.*?\1", "", content,
                     flags=re.IGNORECASE)
    if re.search(r"<(?:p|h[1-6]|ul|ol|table)\b", content, flags=re.IGNORECASE):
        return normalize_body_html(content, fallback_table_context)
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
    wrapped = "".join(
        f"<p>{html.escape(normalize_body_numbering_text(item))}</p>"
        for item in paragraphs
    )
    return normalize_body_html(wrapped, fallback_table_context)


def normalize_chapter_content_contract(raw: dict[str, Any]) -> None:
    if isinstance(raw.get("content"), str):
        return
    blocks = raw.get("blocks")
    if not isinstance(blocks, list):
        return
    normalize_model_blocks(raw)
    parsed = [ContentBlock.model_validate(block) for block in raw.get("blocks", [])]
    raw["content"] = blocks_to_html(parsed)


def _visible_character_count(content: str) -> int:
    visible = html.unescape(re.sub(r"<[^>]+>", "", content))
    return len(re.sub(r"\s+", "", visible))


#: 「最小有效内容」下限：低于单元预算的这个比例即判为响应不足，触发一次局部修复。
#:
#: 详细设计写着「单元预算是质量提示和监控指标，不是硬失败条件……<b>低于最小有效
#: 内容</b>或违反表格/内部字段/事实边界时，才触发一次局部修复」——下限是有的，
#: 只是两侧代码里都没实现过，于是一个只写了四分之一篇幅的章节会一路进到成果里。
#:
#: <b>0.5 这个数字是产品决定，不是推导结果。</b>取值理由：提示词的目标区间是
#: 预算的 80%-115%，下限压到一半远离那个区间，正常波动不会误伤；而拿到不足一半
#: 篇幅的章节确实是废的。取高了会制造重试风暴（Java 侧把 AI_OUTPUT_INVALID 列为
#: 可重试），取低了这道闸门等于不存在。
_MIN_CONTENT_RATIO = 0.5


def chapter_completeness_errors(content: str, word_budget: int) -> list[str]:
    """正文是否短到不成立。

    只查<b>下限</b>。超出预算不在这里判——那是软目标，超了保留全文、不截断、
    不因篇幅重写，只记 OVER_BUDGET。两个方向用同一个判据会让「写多了」
    和「没写完」得到同样的处置，而它们一个是风格问题、一个是缺陷。
    """
    if word_budget <= 0:
        return []
    minimum = round(word_budget * _MIN_CONTENT_RATIO)
    actual = _visible_character_count(content)
    if actual >= minimum:
        return []
    return [
        f"正文可见字符仅{actual}，低于单元最小有效内容{minimum}"
        f"（预算{word_budget}的{int(_MIN_CONTENT_RATIO * 100)}%）；"
        "请按写作任务补足技术内容，不要以套话或同义重复填充"
    ]


def _chapter_budget_warning(content: str, word_budget: int) -> str | None:
    character_count = _visible_character_count(content)
    recommended_maximum = round(word_budget * 1.35)
    if character_count <= recommended_maximum:
        return None
    return (
        f"正文可见字符为{character_count}，超过单元建议预算上限{recommended_maximum}；"
        "内容已保留，最终篇幅由全文页数与排版质量检查统一控制"
    )


def normalize_revision_content_contract(raw: dict[str, Any]) -> None:
    if not isinstance(raw.get("content"), str) and isinstance(raw.get("html"), str):
        raw["content"] = raw["html"]
    if isinstance(raw.get("content"), str):
        return
    normalize_chapter_content_contract(raw)


def _content_summary(value: str) -> str:
    visible = re.sub(r"<[^>]+>", " ", value)
    visible = re.sub(r"\s+", " ", visible).strip()
    return visible[:500]


def normalize_model_blocks(raw: dict[str, Any]) -> None:
    blocks = raw.get("blocks")
    if not isinstance(blocks, list):
        return
    blocks[:] = [
        block for block in blocks
        if not isinstance(block, dict) or block.get("type") != "flowchart"
    ]
    for block in blocks:
        if not isinstance(block, dict):
            continue
        data = block.get("data")
        if isinstance(data, dict):
            for key in ("caption", "note", "rows"):
                if key not in block and key in data:
                    block[key] = data[key]
            if "caption" not in block and isinstance(data.get("title"), str):
                block["caption"] = data["title"]
            if "header" not in block and isinstance(data.get("headers"), list):
                block["header"] = data["headers"]
        items = block.get("items")
        if isinstance(items, list):
            block["items"] = [
                item.get("text", "") if isinstance(item, dict) else item for item in items
            ]


def normalize_outline_tree(raw: dict[str, Any]) -> None:
    nodes = raw.get("nodes")
    if not isinstance(nodes, list):
        return
    valid_nodes = [node for node in nodes if isinstance(node, dict)]
    node_keys = {
        str(node.get("nodeKey", node.get("node_key", "")))
        for node in valid_nodes
        if node.get("nodeKey", node.get("node_key"))
    }
    parent_keys = {
        str(node.get("parentKey", node.get("parent_key", "")))
        for node in valid_nodes
        if node.get("parentKey", node.get("parent_key"))
    }
    normalized = False
    generated: list[dict[str, Any]] = []
    for node in valid_nodes:
        node_key = str(node.get("nodeKey", node.get("node_key", "")))
        level = node.get("level")
        if not node_key or node_key in parent_keys or not isinstance(level, int) or level >= 3:
            continue
        leaf_brief = node.get("taskBrief", node.get("task_brief", ""))
        leaf_keywords = node.get("mustKeywords", node.get("must_keywords", []))
        _set_outline_value(node, "mustKeywords", "must_keywords", [])
        _set_outline_value(node, "scoringPointIds", "scoring_point_ids", [])
        parent_key = node_key
        parent_title = str(node.get("title", "")).strip() or "技术响应"
        for child_level in range(level + 1, 4):
            suffix = "plan" if child_level == 2 else "detail"
            child_key = _unique_outline_key(f"{node_key}-{suffix}", node_keys)
            child_title = (
                f"{parent_title}总体方案" if child_level == 2 else f"{parent_title}详细响应"
            )
            is_leaf = child_level == 3
            child = {
                "nodeKey": child_key,
                "parentKey": parent_key,
                "level": child_level,
                "title": child_title,
                "plannedPages": 0,
                "taskBrief": leaf_brief if is_leaf else "",
                "mustKeywords": leaf_keywords if is_leaf else [],
                # 任务简述和关键词随着叶子下移——它们描述「要写什么」，
                # 换个层级仍然成立。评分点<b>不下移</b>：覆盖关系是
                # 「哪一节响应哪条评分」的事实声明，而这个节点是系统补出来的，
                # 模型从没为它做过那个声明。一并作废的还有指向原节点的 coverage。
                "scoringPointIds": [],
            }
            generated.append(child)
            parent_key = child_key
            parent_title = child_title
        normalized = True
    if generated:
        nodes.extend(generated)
        valid_nodes.extend(generated)

    minimum_children = _ensure_minimum_outline_children(valid_nodes, node_keys)
    if minimum_children:
        nodes.extend(minimum_children)
        valid_nodes.extend(minimum_children)
        normalized = True

    nodes_by_key = {
        str(node.get("nodeKey", node.get("node_key", ""))): node
        for node in valid_nodes
        if node.get("nodeKey", node.get("node_key"))
    }
    legacy_pages: dict[str, int] = {}
    for node in valid_nodes:
        if node.get("level") == 1:
            continue
        node_key = str(node.get("nodeKey", node.get("node_key", "")))
        pages = node.get("plannedPages", node.get("planned_pages", 0))
        ancestor_key: object = node.get("parentKey", node.get("parent_key"))
        visited = {node_key}
        while ancestor_key and str(ancestor_key) not in visited:
            visited.add(str(ancestor_key))
            parent = nodes_by_key.get(str(ancestor_key))
            if parent is None:
                break
            if parent.get("level") == 1:
                if isinstance(pages, int) and pages > 0:
                    root_key = str(parent.get("nodeKey", parent.get("node_key", "")))
                    legacy_pages[root_key] = legacy_pages.get(root_key, 0) + pages
                break
            ancestor_key = parent.get("parentKey", parent.get("parent_key"))
        if pages != 0:
            _set_outline_value(node, "plannedPages", "planned_pages", 0)
            normalized = True

    for node in valid_nodes:
        # 评分点只挂在叶子上（详细设计 §5.3：「每个叶子维护 taskBrief、
        # 必含关键词和评分点 ID」）。非叶子清空，叶子<b>原样保留</b>。
        #
        # 这一行原来写在 level 过滤之前，于是把每一个叶子的评分点也清掉了
        # ——正文阶段据评分点召回冻结的评分原文，清空的表现是每一章都
        # 召不回自己该响应的评分要求，而目录看起来完全正常。
        if node.get("level") != 3:
            _set_outline_value(node, "scoringPointIds", "scoring_point_ids", [])
        if node.get("level") != 1:
            continue
        node_key = str(node.get("nodeKey", node.get("node_key", "")))
        pages = node.get("plannedPages", node.get("planned_pages", 0))
        if not isinstance(pages, int) or pages <= 0:
            _set_outline_value(
                node, "plannedPages", "planned_pages", max(1, legacy_pages.get(node_key, 0))
            )
            normalized = True

    original_keys = [
        str(node.get("nodeKey", node.get("node_key", ""))) for node in valid_nodes
    ]
    ordered_nodes = _order_outline_dicts(valid_nodes)
    ordered_keys = [
        str(node.get("nodeKey", node.get("node_key", ""))) for node in ordered_nodes
    ]
    if ordered_keys != original_keys:
        nodes[:] = ordered_nodes
        normalized = True

    # 覆盖关系由叶子<b>推导</b>，不采用模型给的那一份。
    #
    # 模型给的映射可以指向不存在的、或者已经不是叶子的节点，而它一旦被
    # 采信，界面会显示某条评分「已覆盖」而实际上没有任何章节在响应它。
    # 从叶子推导得到的映射与树永远一致——因为它就是树的一个投影。
    raw["coverage"] = _coverage_from_leaves(valid_nodes)
    if not normalized:
        return
    warnings = raw.setdefault("warnings", [])
    if isinstance(warnings, list):
        warnings.append("目录层级与页数已按规则规整。")


def _branch_blueprint_prompt(request: ChapterDraftRequest) -> dict[str, Any] | None:
    """把分支蓝图裁成这一章能用的样子。

    两件事必须做，而且都不是格式问题：

    <b>去掉 chapterId。</b>它是内部标识，正文提示词里出现内部 id，模型就有机会
    把它写进正文——那会直接出现在交给评审的标书里。这个载荷里所有其它标识
    （requestId、评分点 id、章节 id）都已经被剥掉了，蓝图不能是唯一的漏洞。

    <b>只留本章那一片。</b>蓝图覆盖整个二级分支的全部章节；把兄弟章节的
    技术决策和交付物一并送进来，模型会把它们也写进本章——表现是相邻章节
    互相重复，而每一章单独看都是合理的。
    """
    blueprint = request.branch_blueprint
    if blueprint is None:
        return None
    prompt: dict[str, Any] = {
        "solutionPositioning": blueprint.solution_positioning,
        "sharedDecisions": blueprint.shared_decisions,
        "sharedConstraints": blueprint.shared_constraints,
    }
    if blueprint.assumptions:
        prompt["assumptions"] = blueprint.assumptions
    if blueprint.prohibited_claims:
        prompt["prohibitedClaims"] = blueprint.prohibited_claims
    leaf = next(
        (item for item in blueprint.chapters if item.chapter_id == request.chapter.id),
        None,
    )
    if leaf is not None:
        prompt["chapter"] = {
            "objective": leaf.objective,
            "technicalDecisions": leaf.technical_decisions,
            "implementationActions": leaf.implementation_actions,
            "deliverables": leaf.deliverables,
            "validationMethods": leaf.validation_methods,
            "presentation": leaf.presentation,
        }
    return prompt


def _coverage_from_leaves(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按叶子上的评分点归集出「哪条评分由哪些章节响应」。

    保持首次出现顺序而不是排序：目录的阅读顺序就是评审的阅读顺序，
    按字典序重排会让这张表和目录对不上。
    """
    grouped: dict[str, list[str]] = {}
    for node in nodes:
        if node.get("level") != 3:
            continue
        node_key = str(node.get("nodeKey", node.get("node_key", "")))
        if not node_key:
            continue
        for point in node.get("scoringPointIds", node.get("scoring_point_ids", [])) or []:
            key = str(point).strip()
            if not key:
                continue
            keys = grouped.setdefault(key, [])
            if node_key not in keys:
                keys.append(node_key)
    return [
        {"scoringPointId": point, "nodeKeys": keys} for point, keys in grouped.items()
    ]


def _order_outline_dicts(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def node_key(node: dict[str, Any]) -> str:
        return str(node.get("nodeKey", node.get("node_key", "")))

    def parent_key(node: dict[str, Any]) -> str | None:
        value = node.get("parentKey", node.get("parent_key"))
        return None if value is None else str(value)

    children: dict[str | None, list[dict[str, Any]]] = {}
    for node in nodes:
        children.setdefault(parent_key(node), []).append(node)
    ordered: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        key = node_key(node)
        if not key or key in visited:
            return
        visited.add(key)
        ordered.append(node)
        for child in children.get(key, []):
            visit(child)

    for root in children.get(None, []):
        visit(root)
    for node in nodes:
        visit(node)
    return ordered


def _ensure_minimum_outline_children(
    nodes: list[dict[str, Any]], node_keys: set[str]
) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    children: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        parent = node.get("parentKey", node.get("parent_key"))
        if parent is not None:
            children.setdefault(str(parent), []).append(node)

    for parent_level in (1, 2):
        parents = [
            node for node in [*nodes, *generated] if node.get("level") == parent_level
        ]
        for parent in parents:
            parent_key = str(parent.get("nodeKey", parent.get("node_key", "")))
            if not parent_key:
                continue
            siblings = children.setdefault(parent_key, [])
            while len(siblings) < 2:
                child_level = parent_level + 1
                child_index = len(siblings) + 1
                child_key = _unique_outline_key(
                    f"{parent_key}-required-{child_level}-{child_index}", node_keys
                )
                parent_title = str(parent.get("title", "")).strip() or "技术响应"
                child_title = _generated_outline_title(
                    parent_title, child_level, child_index, siblings
                )
                child = {
                    "nodeKey": child_key,
                    "parentKey": parent_key,
                    "level": child_level,
                    "title": child_title,
                    "plannedPages": 0,
                    "taskBrief": (
                        f"细化{parent_title}的实施方法、控制措施和交付要求，避免与同级章节重复"
                        if child_level == 3
                        else ""
                    ),
                    "mustKeywords": [],
                    "scoringPointIds": [],
                }
                siblings.append(child)
                generated.append(child)
                children.setdefault(child_key, [])
    return generated


def _generated_outline_title(
    parent_title: str, child_level: int, child_index: int,
    siblings: list[dict[str, Any]],
) -> str:
    suffixes = {
        2: ("总体设计", "实施保障", "配套措施"),
        3: ("实施方法", "控制措施", "交付要求"),
    }[child_level]
    existing = {str(node.get("title", "")).strip() for node in siblings}
    for offset in range(len(suffixes)):
        suffix = suffixes[(child_index - 1 + offset) % len(suffixes)]
        candidate = f"{parent_title}{suffix}"
        if candidate not in existing:
            return candidate
    return f"{parent_title}补充方案{child_index}"


def _set_outline_value(
    target: dict[str, Any], alias: str, field_name: str, value: Any
) -> None:
    key = alias if alias in target or field_name not in target else field_name
    target[key] = value


def _unique_outline_key(candidate: str, existing: set[str]) -> str:
    value = candidate
    counter = 2
    while value in existing:
        value = f"{candidate}-{counter}"
        counter += 1
    existing.add(value)
    return value
