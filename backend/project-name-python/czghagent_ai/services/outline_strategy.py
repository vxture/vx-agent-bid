# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-09
import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from czghagent_ai.services.ai_provider import AiProviderDiagnostics
from czghagent_ai.services.structured_output import AiStructuredResult
from czghagent_ai.tender_models import (
    CoverageItem,
    OutlineExpansionNode,
    OutlineExpansionResponse,
    OutlineNode,
    OutlineResponse,
    OutlineSkeletonNode,
    OutlineSkeletonPlan,
    OutlineSkeletonResponse,
)


@dataclass(frozen=True)
class OutlineScale:
    min_level_two: int
    min_level_three: int
    preferred_level_two_min: int
    preferred_level_two_max: int
    preferred_level_three_min: int
    preferred_level_three_max: int
    target_leaf_min: int
    target_leaf_ideal: int
    target_leaf_max: int
    max_level_two: int
    max_leaf: int

    @property
    def phased(self) -> bool:
        return True

    @property
    def target_level_two_min(self) -> int:
        return math.ceil(
            self.target_leaf_ideal / self.preferred_level_three_max
        )

    @property
    def target_level_two_max(self) -> int:
        return max(
            self.target_level_two_min,
            math.floor(
                self.target_leaf_ideal / self.preferred_level_three_min
            ),
        )

    @property
    def level_two_cap(self) -> int:
        """二级目录数的<b>唯一</b>上限：告诉模型的是它，提示用户的也是它。

        含义是「再多，每个二级就分不到两个三级小节」（按篇幅估算的三级数 ÷ 每个二级至少 2 个）。
        建议区间 ``target_level_two_min``–``target_level_two_max`` 与它之间是容差带，不提示。
        此前告诉模型的是 ``max_level_two``，校验器卡的却是另一个更小的数，模型从不知道真正的上限。
        """
        return min(self.max_level_two, self.absolute_level_two_max)

    @property
    def absolute_level_two_max(self) -> int:
        return max(
            self.target_level_two_max,
            math.floor(self.target_leaf_ideal / self.min_level_three),
        )

    def payload(self) -> dict[str, object]:
        return {
            "minLevelTwoChildrenPerLevelOne": self.min_level_two,
            "minLevelThreeChildrenPerLevelTwo": self.min_level_three,
            "preferredLevelTwoChildrenPerLevelOne": {
                "min": self.preferred_level_two_min,
                "max": self.preferred_level_two_max,
            },
            "preferredLevelThreeChildrenPerLevelTwo": {
                "min": self.preferred_level_three_min,
                "max": self.preferred_level_three_max,
            },
            "targetLeafChapters": {
                "min": self.target_leaf_min,
                "ideal": self.target_leaf_ideal,
                "max": self.target_leaf_max,
            },
            "targetLevelTwoChapters": {
                "min": self.target_level_two_min,
                "max": self.target_level_two_max,
            },
            "maxLevelTwoChapters": self.level_two_cap,
            "maxLeafChapters": self.max_leaf,
            "generationMode": "PHASED_QUOTA",
        }


@dataclass(frozen=True)
class OutlineBranchTarget:
    node: OutlineSkeletonNode
    root_title: str
    leaf_count: int


def normalize_skeleton_pages(value: dict[str, Any]) -> None:
    """Keep page allocation system-owned while preserving model-generated structure."""
    nodes = value.get("nodes")
    if not isinstance(nodes, list):
        return
    normalized = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        level = node.get("level")
        expected = 1 if level == 1 else 0
        current = node.get("plannedPages", node.get("planned_pages"))
        if not isinstance(current, int) or (level == 1 and current < 1) or (
            level == 2 and current != 0
        ):
            node["plannedPages"] = expected
            node.pop("planned_pages", None)
            normalized += 1
    if normalized:
        warnings = value.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(f"系统已归一化{normalized}个骨架章节的页数占位。")


def normalize_skeleton(value: dict[str, Any], scale: OutlineScale) -> None:
    """只规整系统拥有的页数，不动模型给的结构。

    这里曾经把「超额」的二级目录按容量公平裁掉：模型的结构被改了，用户却只看到结果。
    现在数量偏差一律保留原样、作为提示展示给用户，由用户决定直接用、编辑还是重新生成。
    """
    del scale
    normalize_skeleton_pages(value)


def build_outline_scale(
    target_pages: int, project_overview: str, technical_scoring: str
) -> OutlineScale:
    # 每个三级目录承担多少页。
    #
    # 短标书的每节略薄（2.6 页），长标书略厚（2.8 页）——长文里章节多了之后，
    # 继续切碎只会制造同义重复的标题，而不是更细的技术分解。
    #
    # 这两个数<b>不是可以随手调的</b>：整条目录链路的配额、二级容量、正文字数预算
    # 都从它们派生。曾经它们被改成 1.5/2.5/2.75，于是 80 页的标书要写 53 个三级节点
    # ——每节 1.5 页。那不会报错，只会让模型被迫把同一件事拆成三个标题，
    # 而评审看到的是一份注水的目录。
    divisor = 2.6 if target_pages <= 200 else 2.8
    base = round(target_pages / divisor)
    base = max(12, min(300, base))
    complexity = _source_complexity(project_overview, technical_scoring)
    bonus = min(round(base * 0.1), max(0, complexity - 6))
    ideal = max(12, min(300, base + bonus))
    # 目标下限保留约 18% 的模型结构容差，避免临界一两个节点导致整单失败。
    minimum = max(12, round(base * 0.85), math.floor(ideal * 0.82))
    maximum_factor = 1.13 if target_pages <= 200 else 1.1
    maximum = min(300, max(minimum, round(ideal * maximum_factor)))
    hard_maximum = min(300, max(maximum, round(ideal * 1.35)))
    max_level_two = max(6, min(120, math.ceil(hard_maximum / 2)))
    return OutlineScale(2, 2, 3, 6, 3, 5, minimum, ideal, maximum,
                        max_level_two, hard_maximum)


#: 三级小节总数偏离按篇幅估算值多少以内不提示。二级目录数的容差带由建议区间与上限之间的
#: 距离给出（见 ``OutlineScale.level_two_cap``），不另设比例。
SCALE_TOLERANCE = 0.2

_CHOICES = "可直接使用，也可在编辑中调整，或重新生成目录。"


def skeleton_structure_errors(response: OutlineSkeletonResponse) -> list[str]:
    """骨架是否<b>能用</b>。只有用不了的情形才算错误、才让模型重来。"""
    if not any(node.level == 1 for node in response.nodes):
        return ["骨架没有任何一级目录"]
    if not any(node.level == 2 for node in response.nodes):
        return ["骨架没有任何二级目录，无法展开三级小节"]
    return []


def skeleton_scale_warnings(
    response: OutlineSkeletonResponse, scale: OutlineScale
) -> list[str]:
    """骨架规模与篇幅估算的偏差。只提示，不拒绝、不裁剪、不让模型重来。"""
    branches = [node for node in response.nodes if node.level == 2]
    warnings: list[str] = []
    if len(branches) > scale.level_two_cap:
        warnings.append(
            f"二级目录共{len(branches)}个，多于按篇幅估算的上限{scale.level_two_cap}个"
            f"（建议{scale.target_level_two_min}至{scale.target_level_two_max}个）：目录会偏细，"
            f"每节篇幅偏短。{_CHOICES}"
        )
    elif len(branches) < scale.target_level_two_min:
        warnings.append(
            f"二级目录仅{len(branches)}个，少于建议的{scale.target_level_two_min}至"
            f"{scale.target_level_two_max}个：每章篇幅偏长，可能覆盖不到全部技术要点。{_CHOICES}"
        )
    missing_briefs = [node.title for node in branches if not node.task_brief.strip()]
    if missing_briefs:
        warnings.append(
            f"{len(missing_briefs)}个二级目录缺少任务简述（如「{missing_briefs[0]}」），"
            "其下三级小节可能不够具体。"
        )
    return warnings


def adapt_scale_to_skeleton(
    skeleton: OutlineSkeletonResponse, scale: OutlineScale
) -> OutlineScale:
    """Adapt the leaf target to the model's valid business skeleton.

    Preconditions:
        - The skeleton already passed structural validation.
        - Each branch can carry between ``min_level_three`` and
          ``preferred_level_three_max`` leaves.
    Side Effects:
        - None; the deviation from the page-based estimate is reported after merging.
    Error Semantics:
        - An empty skeleton is returned unchanged and remains invalid upstream.
    """
    branch_count = sum(node.level == 2 for node in skeleton.nodes)
    if branch_count == 0:
        return scale
    minimum_capacity = branch_count * scale.min_level_three
    maximum_capacity = branch_count * scale.preferred_level_three_max
    target = min(max(scale.target_leaf_ideal, minimum_capacity), maximum_capacity)
    if target == scale.target_leaf_ideal:
        return scale
    # 不另发提示：计划随骨架调整本身不是问题，与篇幅估算的偏差由合并后的
    # outline_scale_warnings 用「多少节、每节多少页」一次说清。
    return replace(
        scale,
        target_leaf_min=min(scale.target_leaf_min, target),
        target_leaf_ideal=target,
        target_leaf_max=max(target, min(scale.target_leaf_max, maximum_capacity)),
    )


def allocate_branch_targets(
    skeleton: OutlineSkeletonResponse, scale: OutlineScale
) -> list[OutlineBranchTarget]:
    roots = {node.node_key: node.title for node in skeleton.nodes if node.level == 1}
    branches = [node for node in skeleton.nodes if node.level == 2]
    minimum_capacity = len(branches) * scale.min_level_three
    maximum_capacity = len(branches) * scale.preferred_level_three_max
    if not minimum_capacity <= scale.target_leaf_ideal <= maximum_capacity:
        raise ValueError("outline skeleton cannot carry the deterministic leaf quota")
    desired = scale.target_leaf_ideal
    counts = [scale.min_level_three] * len(branches)
    remaining = desired - sum(counts)
    priority = sorted(
        range(len(branches)),
        key=lambda index: (
            len(branches[index].task_brief) + 30 * len(branches[index].must_keywords),
            -index,
        ),
        reverse=True,
    )
    while remaining > 0:
        progressed = False
        for index in priority:
            if counts[index] >= scale.preferred_level_three_max:
                continue
            counts[index] += 1
            remaining -= 1
            progressed = True
            if remaining == 0:
                break
        if not progressed:
            break
    return [
        OutlineBranchTarget(node, roots.get(node.parent_key or "", ""), counts[index])
        for index, node in enumerate(branches)
    ]


def expansion_structure_errors(
    response: OutlineExpansionResponse, targets: list[OutlineBranchTarget]
) -> list[str]:
    """三级展开是否<b>能用</b>：只检查节点挂在本批的二级目录下。

    每个二级的三级数量是建议（``preferredLeafCount``），多一两个少一两个都保留原样——
    这里曾经要求逐个精确相等，不等就让模型重来，再不等就整份目录失败，
    而之前的规整步骤还会裁掉多出的、用模板标题补齐缺的。
    """
    expected = {target.node.node_key for target in targets}
    return [
        f"三级目录引用了本批次之外的父节点：{node.parent_key}"
        for node in response.nodes
        if node.parent_key not in expected
    ]


def merge_outline(
    skeleton: OutlineSkeletonResponse,
    expansions: list[OutlineExpansionResponse],
) -> OutlineResponse:
    expanded_by_parent: dict[str, list[OutlineExpansionNode]] = {
        skeleton_node.node_key: []
        for skeleton_node in skeleton.nodes
        if skeleton_node.level == 2
    }
    # 只带骨架阶段系统算出的提示；三级展开里模型自带的 warnings 是自述，不展示给用户。
    warnings = [*skeleton.warnings]
    for expansion in expansions:
        for expansion_node in expansion.nodes:
            expanded_by_parent.setdefault(expansion_node.parent_key, []).append(expansion_node)
    skeleton_children: dict[str, list[OutlineSkeletonNode]] = {}
    for node in skeleton.nodes:
        if node.parent_key:
            skeleton_children.setdefault(node.parent_key, []).append(node)
    output: list[OutlineNode] = []
    existing = {node.node_key for node in skeleton.nodes}
    # 没有展开出三级小节的二级（以及因此没有子节点的一级）从目录里略去并点名。
    # 目录的叶子必须是三级——正文按三级小节生成——所以空的二级留不下来；
    # 而用「…建设内容」「…技术实现」这类模板标题替模型补齐，是在编造目录。
    dropped: list[str] = []
    for root in (node for node in skeleton.nodes if node.level == 1):
        branches = [
            branch for branch in skeleton_children.get(root.node_key, [])
            if expanded_by_parent.get(branch.node_key)
        ]
        dropped.extend(
            branch.title for branch in skeleton_children.get(root.node_key, [])
            if not expanded_by_parent.get(branch.node_key)
        )
        if not branches:
            dropped.append(root.title)
            continue
        output.append(_skeleton_to_outline(root))
        for branch in branches:
            output.append(_skeleton_to_outline(branch))
            for index, leaf in enumerate(expanded_by_parent.get(branch.node_key, []), 1):
                node_key = _unique_key(f"{branch.node_key}-leaf-{index}", existing)
                output.append(OutlineNode(
                    node_key=node_key,
                    parent_key=branch.node_key,
                    level=3,
                    title=leaf.title.strip(),
                    planned_pages=0,
                    task_brief=leaf.task_brief.strip(),
                    must_keywords=leaf.must_keywords,
                    # 评分点原样带过来。同一个构造里 task_brief 和 must_keywords
                    # 都保留了，唯独这个被清空——而正文阶段正是据它召回本章该
                    # 响应的冻结评分原文（§5.3/§5.4）。丢了不报错，
                    # 只是每一章都召不回自己要响应的评分要求。
                    scoring_point_ids=leaf.scoring_point_ids,
                ))
    if dropped:
        warnings.append(
            f"{len(dropped)}个章节没有生成下级小节，已从目录中略去（如「{dropped[0]}」）；"
            "如需要，请在编辑中补回，或重新生成目录。"
        )
    return OutlineResponse(
        nodes=output, coverage=_coverage_from_leaves(output), warnings=warnings
    )


def _coverage_from_leaves(nodes: list[OutlineNode]) -> list[CoverageItem]:
    """按叶子上的评分点归集出「哪条评分由哪些章节响应」。

    分批装配自己拼出整棵树，所以覆盖关系也只能在这里推导——模型每批只看见
    自己那几个分支，谁都给不出全局映射。而从叶子推导出来的映射与树永远一致，
    因为它就是树的一个投影。

    保持首次出现顺序而不是排序：目录的阅读顺序就是评审的阅读顺序。
    """
    grouped: dict[str, list[str]] = {}
    for node in nodes:
        if node.level != 3:
            continue
        for point in node.scoring_point_ids:
            key = point.strip()
            if not key:
                continue
            keys = grouped.setdefault(key, [])
            if node.node_key not in keys:
                keys.append(node.node_key)
    return [
        CoverageItem(scoring_point_id=point, node_keys=keys)
        for point, keys in grouped.items()
    ]


def merged_outline_errors(response: OutlineResponse) -> list[str]:
    """合并后的目录是否<b>能用</b>：至少要有可以写正文的三级小节。"""
    if not any(node.level == 3 for node in response.nodes):
        return ["目录没有任何三级小节，无法生成正文"]
    return []


def outline_scale_warnings(
    response: OutlineResponse, scale: OutlineScale, target_pages: int
) -> list[str]:
    """合并后目录与篇幅估算的偏差。只提示，不拒绝。"""
    leaves = [node for node in response.nodes if node.level == 3]
    warnings: list[str] = []
    ideal = scale.target_leaf_ideal
    if leaves and abs(len(leaves) - ideal) > ideal * SCALE_TOLERANCE:
        direction = "偏细" if len(leaves) > ideal else "偏粗"
        warnings.append(
            f"三级小节共{len(leaves)}个，按{target_pages}页估算约{ideal}个："
            f"目录{direction}，平均每节约{target_pages / len(leaves):.1f}页。{_CHOICES}"
        )
    return warnings


def aggregate_outline_result(
    data: OutlineResponse,
    # 只读诊断与尝试次数。分阶段装配传进来的是带批次划分的 OutlineSkeletonPlan，不是模型原始的骨架响应。
    results: Sequence[
        AiStructuredResult[OutlineSkeletonResponse]
        | AiStructuredResult[OutlineSkeletonPlan]
        | AiStructuredResult[OutlineExpansionResponse]
    ],
) -> AiStructuredResult[OutlineResponse]:
    diagnostics = [result.diagnostics for result in results]
    response_hash = hashlib.sha256(
        "|".join(item.response_hash for item in diagnostics).encode("utf-8")
    ).hexdigest()
    combined = AiProviderDiagnostics(
        finish_reason=diagnostics[-1].finish_reason,
        response_length=sum(item.response_length for item in diagnostics),
        response_hash=response_hash,
        input_tokens=_sum_optional(item.input_tokens for item in diagnostics),
        output_tokens=_sum_optional(item.output_tokens for item in diagnostics),
    )
    return AiStructuredResult(data, combined, sum(result.attempts for result in results))


def _source_complexity(project_overview: str, technical_scoring: str) -> int:
    headings = len(re.findall(r"(?m)^\s{0,3}#{1,6}\s+", technical_scoring))
    scored_items = sum(
        bool(re.search(r"(?:得|赋|满|最高|最低|不计|不得)\s*\d*(?:\.\d+)?\s*分", line))
        for line in technical_scoring.splitlines()
    )
    overview_headings = len(re.findall(r"(?m)^\s{0,3}#{1,6}\s+", project_overview))
    return headings + scored_items + min(5, math.ceil(overview_headings / 2))


def _skeleton_roots_with_two_children(nodes: list[OutlineSkeletonNode]) -> int:
    counts: dict[str, int] = {}
    for node in nodes:
        if node.parent_key:
            counts[node.parent_key] = counts.get(node.parent_key, 0) + 1
    return sum(counts.get(node.node_key, 0) == 2 for node in nodes if node.level == 1)


def _skeleton_to_outline(node: OutlineSkeletonNode) -> OutlineNode:
    return OutlineNode(
        node_key=node.node_key,
        parent_key=node.parent_key,
        level=node.level,
        title=node.title,
        planned_pages=node.planned_pages,
        task_brief=node.task_brief,
        must_keywords=node.must_keywords,
        scoring_point_ids=[],
    )


def _unique_key(candidate: str, existing: set[str]) -> str:
    key = candidate
    counter = 2
    while key in existing:
        key = f"{candidate}-{counter}"
        counter += 1
    existing.add(key)
    return key


def _sum_optional(values: Iterable[int | None]) -> int | None:
    items = [value for value in values if isinstance(value, int)]
    return sum(items) if items else None
