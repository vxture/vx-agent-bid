# GENERATED_BY_AI
# MODEL: gpt-5
# DATE: 2026-08-28
from typing import Generic, Literal, TypeVar

from pydantic import Field, model_validator

from czghagent_ai.models import ApiModel
from czghagent_ai.strategy_models import BidStrategyResponse

AiData = TypeVar("AiData")


class AiResponseDiagnostics(ApiModel):
    finish_reason: str | None = None
    response_length: int = Field(ge=0)
    response_hash: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    attempts: int = Field(ge=1)
    model_code: str | None = None


class AiResponseEnvelope(ApiModel, Generic[AiData]):
    data: AiData
    diagnostics: AiResponseDiagnostics


class SourceSegment(ApiModel):
    locator_type: str
    locator: str
    text: str


class InterpretationRequest(ApiModel):
    request_id: str
    document_id: str
    title: str
    bidding_mode: Literal["OPEN", "BLIND"]
    segments: list[SourceSegment] = Field(min_length=1)


class InterpretationResponse(ApiModel):
    project_overview: str = Field(min_length=1, max_length=6500)
    technical_scoring_requirements: str = Field(min_length=1)


class ProjectOverviewResponse(ApiModel):
    project_overview: str = Field(min_length=1, max_length=6500)


class ProjectOverviewSourceSelection(ApiModel):
    ordered_segment_ids: list[str] = Field(min_length=1, max_length=160)


class ProjectOverviewWindowSelection(ApiModel):
    """分窗口选段时单个窗口的答案。

    与整份文件一次选段的区别只有下限：一个窗口可能整段都是评分办法或投标格式，
    此时正确答案是空数组。沿用 ``min_length=1`` 会逼模型在不相关的段落里硬挑一个。
    """

    ordered_segment_ids: list[str] = Field(max_length=160)


class ProjectOverviewSection(ApiModel):
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=6000)


class ProjectOverviewDraft(ApiModel):
    sections: list[ProjectOverviewSection] = Field(min_length=1, max_length=8)


class TechnicalScoringResponse(ApiModel):
    technical_scoring_requirements: str = Field(min_length=1)


class TechnicalScoringSelectionResponse(ApiModel):
    ordered_clause_ids: list[str] = Field(min_length=1)


class CriterionContract(ApiModel):
    id: str
    type: Literal[
        "PROJECT_OVERVIEW", "TECHNICAL_SCORING", "SCORING", "REJECTION", "FORMAT", "FACT"
    ]
    title: str
    description: str
    score: float | None = None
    source_locator: str = ""
    source_excerpt: str = ""


class ReferenceSummary(ApiModel):
    id: str
    category: str
    name: str
    summary: str


class OutlineRequest(ApiModel):
    request_id: str
    title: str
    target_pages: int = Field(ge=1, le=2000)
    bidding_mode: Literal["OPEN", "BLIND"]
    criteria: list[CriterionContract] = Field(min_length=1)
    references: list[ReferenceSummary] = Field(default_factory=list)


class OutlineNode(ApiModel):
    node_key: str
    parent_key: str | None
    level: int = Field(ge=1, le=3)
    title: str
    planned_pages: int = Field(ge=0, le=2000)
    task_brief: str
    must_keywords: list[str] = Field(default_factory=list)
    scoring_point_ids: list[str] = Field(default_factory=list)


class CoverageItem(ApiModel):
    scoring_point_id: str
    node_keys: list[str]


class Metric(ApiModel):
    name: str
    value: str
    source_locator: str


class Term(ApiModel):
    canonical: str
    forbidden: list[str] = Field(default_factory=list)


class FixedFact(ApiModel):
    name: str
    value: str
    source_locator: str


class FrozenDictionary(ApiModel):
    metrics: list[Metric] = Field(default_factory=list)
    terms: list[Term] = Field(default_factory=list)
    fixed_facts: list[FixedFact] = Field(default_factory=list)


class OutlineResponse(ApiModel):
    nodes: list[OutlineNode] = Field(min_length=1)
    coverage: list[CoverageItem] = Field(default_factory=list)
    dictionary: FrozenDictionary = Field(default_factory=FrozenDictionary)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tree(self) -> "OutlineResponse":
        nodes = {node.node_key: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("outline node keys must be unique")
        for node in self.nodes:
            if node.level == 1 and node.parent_key is not None:
                raise ValueError("level-one outline nodes cannot have a parent")
            if node.level > 1:
                parent = nodes.get(node.parent_key or "")
                if parent is None or parent.level != node.level - 1:
                    raise ValueError("outline parent/level relationship is invalid")
        parent_keys = {node.parent_key for node in self.nodes if node.parent_key}
        leaves = [node for node in self.nodes if node.node_key not in parent_keys]
        if not leaves or any(node.level != 3 for node in leaves):
            raise ValueError("all outline leaves must be level three")
        child_counts: dict[str, int] = {}
        for node in self.nodes:
            if node.parent_key:
                child_counts[node.parent_key] = child_counts.get(node.parent_key, 0) + 1
        if any(
            child_counts.get(node.node_key, 0) < 2
            for node in self.nodes
            if node.level in {1, 2}
        ):
            raise ValueError("every level-one and level-two outline node needs two children")
        roots = [node for node in self.nodes if node.level == 1]
        if not roots or any(node.planned_pages < 1 for node in roots):
            raise ValueError("level-one outline nodes must have a page budget")
        if any(node.planned_pages != 0 for node in self.nodes if node.level > 1):
            raise ValueError("level-two and level-three nodes cannot have a page budget")
        return self


class OutlineSkeletonNode(ApiModel):
    node_key: str
    parent_key: str | None
    level: Literal[1, 2]
    title: str
    planned_pages: int = Field(ge=0, le=2000)
    task_brief: str = ""
    must_keywords: list[str] = Field(default_factory=list)


class OutlineSkeletonResponse(ApiModel):
    nodes: list[OutlineSkeletonNode] = Field(min_length=3)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tree(self) -> "OutlineSkeletonResponse":
        nodes = {node.node_key: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("outline skeleton node keys must be unique")
        child_counts: dict[str, int] = {}
        for node in self.nodes:
            if node.level == 1 and node.parent_key is not None:
                raise ValueError("level-one skeleton nodes cannot have a parent")
            if node.level == 2:
                parent = nodes.get(node.parent_key or "")
                if parent is None or parent.level != 1:
                    raise ValueError("level-two skeleton parent is invalid")
                child_counts[parent.node_key] = child_counts.get(parent.node_key, 0) + 1
            if node.level == 1 and node.planned_pages < 1:
                raise ValueError("level-one skeleton nodes need a page budget")
            if node.level == 2 and node.planned_pages != 0:
                raise ValueError("level-two skeleton nodes cannot have a page budget")
        roots = [node for node in self.nodes if node.level == 1]
        if not roots or any(child_counts.get(node.node_key, 0) < 2 for node in roots):
            raise ValueError("every level-one skeleton node needs two children")
        return self


class OutlineExpansionNode(ApiModel):
    parent_key: str
    title: str
    task_brief: str
    must_keywords: list[str] = Field(default_factory=list)
    scoring_point_ids: list[str] = Field(default_factory=list)


class OutlineExpansionResponse(ApiModel):
    nodes: list[OutlineExpansionNode] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_nodes(self) -> "OutlineExpansionResponse":
        identities = {
            (node.parent_key.strip(), node.title.strip()) for node in self.nodes
        }
        if len(identities) != len(self.nodes):
            raise ValueError("expanded outline titles must be unique within each parent")
        if any(not node.parent_key.strip() or not node.title.strip() for node in self.nodes):
            raise ValueError("expanded outline parent and title cannot be blank")
        return self


class OutlineBranchTargetContract(ApiModel):
    node_key: str = Field(min_length=1, max_length=160)
    root_title: str = Field(max_length=200)
    title: str = Field(min_length=1, max_length=200)
    task_brief: str = Field(max_length=4000)
    must_keywords: list[str] = Field(default_factory=list, max_length=20)
    preferred_leaf_count: int = Field(ge=2, le=5)


class OutlineSkeletonPlan(ApiModel):
    nodes: list[OutlineSkeletonNode] = Field(min_length=3)
    warnings: list[str] = Field(default_factory=list)
    batches: list[list[OutlineBranchTargetContract]] = Field(min_length=1)
    scoring_point_ids: list[str] = Field(default_factory=list)


class OutlineSkeletonStageRequest(ApiModel):
    outline: OutlineRequest
    strategy: BidStrategyResponse


class OutlineExpansionStageRequest(ApiModel):
    outline: OutlineRequest
    strategy: BidStrategyResponse
    batch_index: int = Field(ge=1)
    branches: list[OutlineBranchTargetContract] = Field(min_length=1, max_length=6)


class OutlineAssemblyRequest(ApiModel):
    outline: OutlineRequest
    skeleton: OutlineSkeletonPlan
    expansions: list[OutlineExpansionResponse] = Field(min_length=1)


class ContentBlock(ApiModel):
    type: Literal["heading", "paragraph", "bulletList", "orderedList", "table"]
    level: int | None = Field(default=None, ge=1, le=6)
    text: str = ""
    items: list[str] = Field(default_factory=list)
    caption: str = ""
    note: str = ""
    header: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class ChapterContract(ApiModel):
    id: str
    title: str
    planned_pages: int = Field(ge=0)
    task_brief: str = ""
    must_keywords: list[str] = Field(default_factory=list)
    scoring_point_ids: list[str] = Field(default_factory=list)


class BranchContract(ApiModel):
    id: str
    title: str = Field(min_length=1, max_length=200)
    task_brief: str = Field(default="", max_length=4000)
    must_keywords: list[str] = Field(default_factory=list, max_length=20)


class BranchBlueprintRequest(ApiModel):
    request_id: str
    bid_title: str
    bidding_mode: Literal["OPEN", "BLIND"]
    solution_contract: str = Field(default="", max_length=24000)
    branch: BranchContract
    chapters: list[ChapterContract] = Field(min_length=1, max_length=12)
    criteria: list[CriterionContract]
    dictionary: FrozenDictionary = Field(default_factory=FrozenDictionary)
    writing_bible: str = Field(default="", max_length=6000)
    term_registry: str = Field(default="", max_length=6000)
    commitment_registry: str = Field(default="", max_length=6000)


class LeafBlueprint(ApiModel):
    chapter_id: str
    objective: str = Field(min_length=10, max_length=400)
    technical_decisions: list[str] = Field(min_length=1, max_length=5)
    implementation_actions: list[str] = Field(min_length=2, max_length=8)
    deliverables: list[str] = Field(min_length=1, max_length=5)
    validation_methods: list[str] = Field(min_length=1, max_length=5)
    presentation: str = Field(min_length=2, max_length=120)


class BranchBlueprint(ApiModel):
    solution_positioning: str = Field(min_length=20, max_length=800)
    shared_decisions: list[str] = Field(min_length=1, max_length=8)
    shared_constraints: list[str] = Field(min_length=1, max_length=8)
    chapters: list[LeafBlueprint] = Field(min_length=1, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    prohibited_claims: list[str] = Field(default_factory=list, max_length=8)


class ChapterDraftRequest(ApiModel):
    request_id: str
    bid_title: str
    bidding_mode: Literal["OPEN", "BLIND"]
    chapter: ChapterContract
    # Kept optional for compatibility with the stable chapter-writing contract.
    branch_blueprint: BranchBlueprint | None = None
    criteria: list[CriterionContract]
    dictionary: FrozenDictionary = Field(default_factory=FrozenDictionary)
    evidence: list[SourceSegment] = Field(default_factory=list)
    writing_plan: str = ""
    style_profile: str = ""
    previous_summary: str = ""
    previous_prose: str = ""
    chapter_opening: str = ""
    recent_table_caption: str = ""
    repetition_avoidance: list[str] = Field(default_factory=list)
    next_brief: str = ""
    word_budget: int = Field(ge=1, le=100000)
    unit_index: int = Field(default=0, ge=0)
    unit_count: int = Field(default=1, ge=1)
    unit_title: str = ""
    writing_bible: str = ""
    term_registry: str = ""
    commitment_registry: str = ""


class DraftTerm(ApiModel):
    term: str
    definition: str


class Commitment(ApiModel):
    text: str
    source_ref: str = ""


class ChapterDraftResponse(ApiModel):
    blocks: list[ContentBlock]
    summary: str
    terms: list[DraftTerm] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    html: str = ""


class ChapterContentResponse(ApiModel):
    content: str = Field(min_length=1)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class RevisionRequest(ApiModel):
    request_id: str
    mode: Literal["REWRITE", "REPHRASE", "POLISH", "COMPACT"]
    selected_html: str
    before_context: str = ""
    after_context: str = ""
    instruction: str = ""
    protected_facts: list[str] = Field(default_factory=list)
    dictionary: FrozenDictionary = Field(default_factory=FrozenDictionary)


class RevisionResponse(ApiModel):
    blocks: list[ContentBlock]
    change_summary: str
    preserved_facts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    html: str = ""


class RevisionContentResponse(ApiModel):
    content: str = Field(min_length=1)
    change_summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class ReviewRequest(ApiModel):
    request_id: str
    payload: dict[str, object]


class ReviewIssue(ApiModel):
    severity: Literal["ERROR", "WARNING"]
    code: str
    chapter_id: str
    message: str
    suggestion: str
    source_refs: list[str] = Field(default_factory=list)


class ReviewCoverage(ApiModel):
    total: int = 0
    covered: int = 0
    missing_scoring_point_ids: list[str] = Field(default_factory=list)


class ReviewResponse(ApiModel):
    passed: bool
    issues: list[ReviewIssue] = Field(default_factory=list)
    coverage: ReviewCoverage = Field(default_factory=ReviewCoverage)
    warnings: list[str] = Field(default_factory=list)
    review_summary: str = Field(default="", max_length=3000)
