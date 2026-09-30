# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-09
import asyncio
from typing import Any

from czghagent_ai.services.ai_provider import AiProviderOutputError
from czghagent_ai.services.bid_strategy import (
    BidStrategyPlanner,
    strategy_prompt_context,
    strategy_scoring_point_ids,
)
from czghagent_ai.services.outline_strategy import (
    OutlineBranchTarget,
    OutlineScale,
    adapt_scale_to_skeleton,
    aggregate_outline_result,
    allocate_branch_targets,
    build_outline_scale,
    expansion_structure_errors,
    merge_outline,
    merged_outline_errors,
    normalize_skeleton,
    outline_scale_warnings,
    skeleton_scale_warnings,
    skeleton_structure_errors,
)
from czghagent_ai.services.structured_output import AiStructuredExecutor, AiStructuredResult
from czghagent_ai.strategy_models import BidStrategyResponse
from czghagent_ai.tender_models import (
    OutlineBranchTargetContract,
    OutlineExpansionResponse,
    OutlineRequest,
    OutlineResponse,
    OutlineSkeletonNode,
    OutlineSkeletonPlan,
    OutlineSkeletonResponse,
)

#: 一批最多几个二级分支。
#:
#: 分批不是为了并发，是为了**可恢复**：一次大标书的三级展开有十几批，
#: 单批失败只重跑那一批。批次太大会让一次失败拖垮更多已经成功的工作，
#: 太小则把固定的提示词开销乘以批数。
BATCH_SIZE = 6


class AdaptiveOutlinePlanner:
    """目录生成的四个阶段：策略 → 骨架 → 分批展开 → 确定性装配。

    每个阶段**既能被一次性编排**（``plan_result``），**也能单独调用**。
    两条路径共用同一批实现，这是刻意的：分成两套的表现是分阶段接口和一次性
    接口对同一份输入给出不同的目录，而那种分叉没有任何症状——两边各自看都对。

    分阶段存在的理由是可恢复：一次 500 页标书的展开有十几批，
    单批失败只该重跑那一批，而不是整份目录重来。
    """

    def __init__(self, executor: AiStructuredExecutor) -> None:
        self._executor = executor
        self._strategy = BidStrategyPlanner(executor)

    async def plan_result(
        self, request: OutlineRequest
    ) -> AiStructuredResult[OutlineResponse]:
        strategy = await self.plan_strategy_result(request)
        skeleton = await self.plan_skeleton_result(request, strategy.data)
        expansions = await self._expand_batches(
            request, strategy.data, skeleton.data.batches
        )
        return self.assemble(request, skeleton, expansions)

    # ── 阶段一：响应策略 ────────────────────────────────────────────────────

    async def plan_strategy_result(
        self, request: OutlineRequest
    ) -> AiStructuredResult[BidStrategyResponse]:
        """先想清楚怎么响应，再决定目录长什么样。

        策略给出的每条评分响应会被编成稳定的 ``SP-00N``，一路传到三级节点上，
        正文阶段据此召回本章该响应的评分原文。没有这一步，目录只是一棵结构树，
        和评分表之间没有任何可追溯的连接。
        """
        payload, _ = self._payload(request)
        return await self._strategy.plan_result(request.request_id, payload)

    # ── 阶段二：一二级骨架 ──────────────────────────────────────────────────

    async def plan_skeleton_result(
        self, request: OutlineRequest, strategy: BidStrategyResponse
    ) -> AiStructuredResult[OutlineSkeletonPlan]:
        payload, scale = self._payload(request, strategy)
        skeleton = await self._executor.execute_result(
            "outline_skeleton_planning",
            payload,
            f"{request.request_id}-outline-skeleton",
            OutlineSkeletonResponse,
            object_name="技术标一二级目录骨架",
            schema_version="outline-skeleton-v2",
            normalizer=lambda response: normalize_skeleton(response, scale),
            semantic_validator=skeleton_structure_errors,
        )
        # 规模偏差只提示：模型的结构原样保留，由用户判断（直接用、编辑或重新生成）。
        skeleton.data.warnings.extend(skeleton_scale_warnings(skeleton.data, scale))
        # 分批在**骨架阶段就定下来并发出去**，而不是留给调用方自己切。
        # 调用方各切各的，重跑一批时的分组就可能和上一次不同，
        # 于是「只重跑第 3 批」重跑的其实是另外一批分支。
        effective_scale = adapt_scale_to_skeleton(skeleton.data, scale)
        targets = allocate_branch_targets(skeleton.data, effective_scale)
        batches = [
            [_to_contract(target) for target in targets[index:index + BATCH_SIZE]]
            for index in range(0, len(targets), BATCH_SIZE)
        ]
        plan = OutlineSkeletonPlan(
            nodes=skeleton.data.nodes,
            warnings=skeleton.data.warnings,
            batches=batches or [[]],
            scoring_point_ids=strategy_scoring_point_ids(strategy),
        )
        return AiStructuredResult(plan, skeleton.diagnostics, skeleton.attempts)

    # ── 阶段三：三级展开（按批） ────────────────────────────────────────────

    async def plan_expansion_result(
        self,
        request: OutlineRequest,
        strategy: BidStrategyResponse,
        batch_index: int,
        branches: list[OutlineBranchTargetContract],
    ) -> AiStructuredResult[OutlineExpansionResponse]:
        payload, _ = self._payload(request, strategy)
        targets = [_from_contract(branch) for branch in branches]
        return await self._executor.execute_result(
            "outline_branch_expansion",
            self._expansion_payload(payload, targets),
            f"{request.request_id}-outline-expansion-{batch_index}",
            OutlineExpansionResponse,
            object_name=f"技术标三级目录第{batch_index}批",
            schema_version="outline-expansion-v2",
            semantic_validator=lambda response: expansion_structure_errors(
                response, targets
            ),
        )

    # ── 阶段四：确定性装配 ──────────────────────────────────────────────────

    def assemble(
        self,
        request: OutlineRequest,
        skeleton: AiStructuredResult[OutlineSkeletonPlan],
        expansions: list[AiStructuredResult[OutlineExpansionResponse]],
    ) -> AiStructuredResult[OutlineResponse]:
        """把骨架和各批展开合成一棵树。**这一步不调模型。**

        合并、编号、覆盖检查和页数归一全部是确定性代码——让模型来做这件事，
        意味着同样的输入可能装出不同的树，而重跑一批就会改变整份目录。
        """
        _, scale = self._payload(request)
        skeleton_response = OutlineSkeletonResponse(
            nodes=skeleton.data.nodes, warnings=skeleton.data.warnings
        )
        merged = merge_outline(
            skeleton_response, [result.data for result in expansions]
        )
        errors = merged_outline_errors(merged)
        if errors:
            raise AiProviderOutputError("目录确定性合并失败：" + "；".join(errors))
        # 与篇幅估算的偏差按<b>页数原始估算</b>比，而不是按随骨架调整后的计划比：
        # 用户关心的是「100 页写成了几节」，不是模型有没有照着自己的骨架展开。
        merged.warnings.extend(outline_scale_warnings(merged, scale, request.target_pages))
        result = aggregate_outline_result(merged, [skeleton, *expansions])
        self._balance_top_level_pages(result.data, request.target_pages)
        return result

    async def _expand_batches(
        self,
        request: OutlineRequest,
        strategy: BidStrategyResponse,
        batches: list[list[OutlineBranchTargetContract]],
    ) -> list[AiStructuredResult[OutlineExpansionResponse]]:
        semaphore = asyncio.Semaphore(4)

        async def expand(
            index: int, batch: list[OutlineBranchTargetContract]
        ) -> AiStructuredResult[OutlineExpansionResponse]:
            async with semaphore:
                return await self.plan_expansion_result(request, strategy, index, batch)

        return list(await asyncio.gather(*(
            expand(index, batch)
            for index, batch in enumerate(batches, 1)
            if batch
        )))

    def _payload(
        self, request: OutlineRequest, strategy: BidStrategyResponse | None = None
    ) -> tuple[dict[str, Any], OutlineScale]:
        overview = next(
            (item.description for item in request.criteria if item.type == "PROJECT_OVERVIEW"),
            "",
        )
        scoring = next(
            (item.description for item in request.criteria if item.type == "TECHNICAL_SCORING"),
            "",
        )
        scale = build_outline_scale(request.target_pages, overview, scoring)
        payload: dict[str, Any] = {
            "title": request.title,
            "targetPages": request.target_pages,
            "biddingMode": request.bidding_mode,
            "projectOverview": overview,
            "technicalScoringRequirements": scoring,
            "outlineScale": scale.payload(),
            "outlineReferences": [
                {"name": item.name, "content": item.summary}
                for item in request.references if item.category == "OUTLINE"
            ],
        }
        if strategy is not None:
            payload["strategy"] = strategy_prompt_context(strategy)
        return payload, scale

    def _expansion_payload(
        self, payload: dict[str, Any], targets: list[OutlineBranchTarget]
    ) -> dict[str, Any]:
        return {
            "title": payload["title"],
            "biddingMode": payload["biddingMode"],
            "projectOverview": payload["projectOverview"],
            "technicalScoringRequirements": payload["technicalScoringRequirements"],
            "branches": [
                {
                    "parentKey": target.node.node_key,
                    "rootTitle": target.root_title,
                    "title": target.node.title,
                    "taskBrief": target.node.task_brief,
                    "mustKeywords": target.node.must_keywords,
                    "preferredLeafCount": target.leaf_count,
                }
                for target in targets
            ],
        }

    def _balance_top_level_pages(self, result: OutlineResponse, target_pages: int) -> None:
        roots = [node for node in result.nodes if node.level == 1]
        if not roots:
            raise AiProviderOutputError("Outline does not contain a level-one chapter")
        for node in result.nodes:
            if node.level > 1:
                node.planned_pages = 0
        current = sum(max(1, node.planned_pages) for node in roots)
        for node in roots:
            node.planned_pages = max(1, node.planned_pages)
        difference = target_pages - current
        cursor = 0
        while difference and cursor <= (target_pages + current + len(roots)) * 2:
            root = roots[cursor % len(roots)]
            if difference > 0:
                root.planned_pages += 1
                difference -= 1
            elif root.planned_pages > 1:
                root.planned_pages -= 1
                difference += 1
            cursor += 1
        if difference:
            raise AiProviderOutputError("Target page budget cannot be balanced")
        if current != target_pages:
            result.warnings.append("AI page allocation was normalized to the requested total.")


def _to_contract(target: OutlineBranchTarget) -> OutlineBranchTargetContract:
    return OutlineBranchTargetContract(
        node_key=target.node.node_key,
        root_title=target.root_title,
        title=target.node.title,
        task_brief=target.node.task_brief,
        must_keywords=target.node.must_keywords,
        preferred_leaf_count=target.leaf_count,
    )


def _from_contract(contract: OutlineBranchTargetContract) -> OutlineBranchTarget:
    """把契约还原成展开阶段要的目标。

    ``parent_key`` 和 ``level`` 在这里是恒定值：展开阶段只用 ``node_key`` 做
    ``parentKey``、用标题和任务简述写提示词，树形关系由装配阶段从骨架重建。
    把它们塞进契约只会多两个调用方可以填错、而且填错了也没人发现的字段。
    """
    return OutlineBranchTarget(
        node=OutlineSkeletonNode(
            node_key=contract.node_key,
            parent_key=None,
            level=2,
            title=contract.title,
            planned_pages=0,
            task_brief=contract.task_brief,
            must_keywords=contract.must_keywords,
        ),
        root_title=contract.root_title,
        leaf_count=contract.preferred_leaf_count,
    )
