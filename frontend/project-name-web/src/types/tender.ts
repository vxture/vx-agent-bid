// GENERATED_BY_AI
// MODEL: gpt-5
// DATE: 2026-08-02
export type BidStep = 'SETUP' | 'INTERPRETATION' | 'OUTLINE' | 'CONTENT'
export type BidStatus =
  | 'DRAFT'
  | 'PARSING'
  | 'INTERPRETATION_READY'
  | 'OUTLINE_GENERATING'
  | 'OUTLINE_READY'
  | 'GENERATING'
  | 'GENERATION_PAUSED'
  | 'CONTENT_READY'
  | 'LAYOUT_QUEUED'
  | 'LAYOUT_RUNNING'
  | 'COMPLETED'
  | 'EXPORTED'
  | 'FAILED'
export type BidMode = 'OPEN' | 'BLIND'
export type InterpretationObjectType = 'PROJECT_OVERVIEW' | 'TECHNICAL_SCORING'
export type InterpretationObjectStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
export type CriterionType =
  | InterpretationObjectType
  | 'SCORING'
  | 'REJECTION'
  | 'FORMAT'
  | 'FACT'
export type AssetCategory = 'TEMPLATE' | 'OUTLINE' | 'GALLERY'

export type BidSetupInput = {
  title: string
  targetPages: number
  biddingMode: BidMode
}

export type BidDocument = {
  id: string
  ownerId: string
  code: string
  writingMethod: 'SCORING_CRITERIA'
  title: string
  targetPages: number
  biddingMode: BidMode
  workflowStep: BidStep
  status: BidStatus
  contentStale: boolean
  errorMessage: string | null
  createdAt: string
  updatedAt: string
  revision: number
}

export type TenderSourceFile = {
  id: string
  originalFileName: string
  mediaType: string
  fileSize: number
  parseStatus: 'PENDING' | 'PARSING' | 'SUCCEEDED' | 'FAILED'
  parseStage:
    | 'PENDING'
    | 'QUEUED'
    | 'EXTRACTING'
    | 'EXTRACTED'
    | 'PROJECT_OVERVIEW'
    | 'TECHNICAL_SCORING'
    | 'SAVING'
    | 'COMPLETE'
    | 'FAILED'
  parseProgress: number
  errorMessage: string | null
  overviewStatus: InterpretationObjectStatus
  overviewErrorMessage: string | null
  scoringStatus: InterpretationObjectStatus
  scoringErrorMessage: string | null
  uploadedAt: string
  parseStartedAt: string | null
  parseFinishedAt: string | null
}

export type BidCriterion = {
  id: string
  type: CriterionType
  title: string
  description: string
  score: number | null
  sourceExcerpt: string
  sourceLocator: string
  scope: 'TECHNICAL' | 'COMMERCIAL' | 'MIXED' | 'FORMAT'
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  sortOrder: number
  manuallyEdited: boolean
}

export type BidOutlineNode = {
  id: string
  parentId: string | null
  level: number
  title: string
  plannedPages: number
  sortOrder: number
  revision: number
  taskBrief: string
  mustKeywords: string[]
  scoringPointIds: string[]
}

export type BidChapter = {
  id: string
  outlineNodeId: string
  title: string
  content: string
  generationStatus: 'PENDING' | 'GENERATING' | 'READY' | 'FAILED' | 'MANUAL'
  updatedAt: string
  revision: number
}

export type BidChapterSummary = Omit<BidChapter, 'content'> & {
  tableCount: number
}

export type BidChapterDetail = {
  chapter: BidChapter
  reviewIssues: BidReviewIssue[]
}

export type BidGenerationTask = {
  id: string
  status: 'PENDING' | 'RUNNING' | 'PAUSED' | 'SUCCEEDED' | 'FAILED'
  totalUnits: number
  completedUnits: number
  errorMessage: string | null
  createdAt: string
  finishedAt: string | null
}

export type BidOutlineTask = {
  id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  stage: 'QUEUED' | 'PREPARING' | 'GENERATING' | 'SAVING' | 'COMPLETE' | 'FAILED'
  progress: number
  inputRevision: number
  workflowRunId: string | null
  errorMessage: string | null
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  /** 目录生成的提示（规模偏差、略去的空章节）。只提示，不代表失败。 */
  warnings: string[]
}

export type BidFrozenFact = {
  id: string
  type: 'METRIC' | 'TERM' | 'FIXED_FACT'
  name: string
  value: string
  sourceLocator: string
  forbiddenValues: string[]
  sortOrder: number
}

export type BidGenerationUnit = {
  id: string
  taskId: string
  chapterId: string
  unitIndex: number
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'SKIPPED'
  attemptCount: number
  wordBudget: number
  summary: string | null
  errorMessage: string | null
  updatedAt: string
}

export type BidGenerationEvent = {
  id: string
  taskId: string
  chapterId: string | null
  type: string
  message: string
  occurredAt: string
}

export type BidReviewIssue = {
  id: string
  chapterId: string | null
  severity: 'ERROR' | 'WARNING' | 'INFO'
  code: string
  message: string
  suggestion: string
  status: 'OPEN' | 'RESOLVED'
}

export type BidLayoutJob = {
  id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  workflowRunId: string | null
  inputHash: string
  targetPages: number
  actualPages: number | null
  qaStatus: 'PENDING' | 'PASSED' | 'WARNING' | 'FAILED' | null
  qaSummary: string | null
  errorMessage: string | null
  createdAt: string
  finishedAt: string | null
}

export type BidProductionState = {
  interpretationStatus: 'DRAFT' | 'REVIEW' | 'FROZEN'
  interpretationVersion: number
  interpretationHash: string | null
  outlineStatus: 'DRAFT' | 'REVIEW' | 'FROZEN'
  outlineVersion: number
  outlineHash: string | null
  contentStatus: 'DRAFT' | 'REVIEW' | 'FROZEN'
  contentVersion: number
  contentHash: string | null
  staleReason: string | null
  frozenFacts: BidFrozenFact[]
  generationUnits: BidGenerationUnit[]
  generationEvents: BidGenerationEvent[]
  reviewIssues: BidReviewIssue[]
  layoutJob: BidLayoutJob | null
}

export type SectionRevisionMode = 'REWRITE' | 'REPHRASE' | 'POLISH'

export type SectionRevisionCandidate = {
  id: string
  mode: SectionRevisionMode
  baseRevision: number
  replacementHtml: string
  changeSummary: string
  preservedFacts: string[]
  warnings: string[]
}

export type BidExport = {
  id: string
  bidId: string
  version: number
  fileName: string
  fileSize: number
  createdAt: string
}

export type BidWorkspace = {
  bid: BidDocument
  sourceFile: TenderSourceFile | null
  criteria: BidCriterion[]
  outline: BidOutlineNode[]
  chapters: BidChapter[]
  outlineTask: BidOutlineTask | null
  generationTask: BidGenerationTask | null
  selectedAssetIds: string[]
  exports: BidExport[]
  production: BidProductionState
}

export type BidMetadata = Pick<
  BidWorkspace,
  | 'bid'
  | 'sourceFile'
  | 'outlineTask'
  | 'generationTask'
  | 'selectedAssetIds'
  | 'exports'
  | 'production'
>

export type BidOutlineView = {
  nodes: BidOutlineNode[]
  chapters: BidChapterSummary[]
}

export type BidGenerationProgress = {
  taskId: string | null
  status: 'IDLE' | BidGenerationTask['status']
  totalUnits: number
  completedUnits: number
  progress: number
  errorMessage: string | null
  createdAt: string | null
  finishedAt: string | null
  recentEvents: BidGenerationEvent[]
}

export type BidSummary = {
  id: string
  code: string
  title: string
  targetPages: number
  biddingMode: BidMode
  workflowStep: BidStep
  status: BidStatus
  contentStale: boolean
  completedChapters: number
  totalChapters: number
  hasExport: boolean
  layoutStatus: BidLayoutJob['status'] | null
  qaStatus: BidLayoutJob['qaStatus']
  actualPages: number | null
  latestExportVersion: number | null
  createdAt: string
  updatedAt: string
}

export type BidReferenceAsset = {
  id: string
  ownerId: string
  category: AssetCategory
  displayName: string
  originalFileName: string
  mediaType: string
  fileSize: number
  createdAt: string
  updatedAt: string
  revision: number
}

export type CriterionInput = Pick<
  BidCriterion,
  | 'id'
  | 'type'
  | 'title'
  | 'description'
  | 'score'
  | 'sourceExcerpt'
  | 'sourceLocator'
  | 'scope'
  | 'confidence'
>

export type OutlineNodeInput = {
  clientId: string
  parentClientId: string | null
  level: number
  title: string
  plannedPages: number
  taskBrief: string
  mustKeywords: string[]
  scoringPointIds: string[]
}
