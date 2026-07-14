export type VideoStatus =
  | 'pending'
  | 'queued'
  | 'processing'
  | 'audio_done'
  | 'transcribing'
  | 'transcribed'
  | 'analyzing'
  | 'done'
  | 'transcription_failed'
  | 'analysis_failed'
  | string

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type VideoProcessStage = 'current' | 'audio' | 'transcription' | 'analysis'

export interface TagCount {
  tag: string
  count: number
}

export interface CreatorSummary {
  platform: string
  secUid: string
  name: string | null
  videoCount: number
  completedCount: number
  topTags: string[]
  updatedAt: string | null
}

export interface VideoSummary {
  id: number
  platform: string
  videoId: string
  creatorSecUid: string
  creatorName: string | null
  description: string | null
  summary: string | null
  tags: string[]
  keyPoints: string[]
  publishedAt: string | null
  status: VideoStatus
  updatedAt: string | null
}

export interface TranscriptSegment {
  start: number
  end: number
  text: string
}

export interface KeyPointEvidence {
  keyPointIndex: number
  segmentIndex: number
  segmentCount: number
  start: number
  end: number
  text: string
  score: number
}

export interface SearchMatch {
  matchType: string
  text: string
  start: number | null
  end: number | null
  segmentIndex: number | null
  segmentCount: number
}

export interface SearchHit extends VideoSummary {
  match: SearchMatch
}

export interface VideoDetail extends VideoSummary {
  transcript: string | null
  segments: TranscriptSegment[]
  keyPointEvidence: KeyPointEvidence[]
  language: string | null
  audioSize: number | null
  audioUrl: string | null
  transcriptionModel: string | null
  analysisModel: string | null
}

export interface CreatorPointSource {
  videoId: number
  title: string
  publishedAt: string | null
  start: number | null
  end: number | null
  segmentIndex: number | null
  excerpt: string | null
}

export interface CreatorInsight {
  text: string
  occurrenceCount: number
  sources: CreatorPointSource[]
}

export interface RepresentativeVideo extends VideoSummary {
  reason: string
}

export interface CreatorProfile {
  overview: string
  analyzedVideoCount: number
  mainThemes: TagCount[]
  insights: CreatorInsight[]
  representativeVideos: RepresentativeVideo[]
  recentVideos: VideoSummary[]
}

export interface DashboardResponse {
  creatorCount: number
  videoCount: number
  completedCount: number
  statusCounts: Record<string, number>
  topTags: TagCount[]
  recentVideos: VideoSummary[]
}

export interface CreatorListResponse {
  items: CreatorSummary[]
  total: number
}

export interface CreatorDetailResponse {
  creator: CreatorSummary
  topTags: TagCount[]
  videos: VideoSummary[]
  profile: CreatorProfile
}

export interface VideoListResponse {
  items: VideoSummary[]
  total: number
}

export interface TagListResponse {
  items: TagCount[]
}

export interface SearchResponse {
  items: SearchHit[]
  total: number
}

export interface SemanticIndexStatus {
  ready: boolean
  model: string | null
  videoCount: number
  chunkCount: number
  indexedAt: string | null
  autoSync: boolean
}

export interface SemanticMatch {
  sourceType: 'transcript' | 'analysis' | string
  text: string
  start: number | null
  end: number | null
  segmentIndex: number | null
  segmentCount: number
  score: number
  semanticScore: number
  keywordScore: number
}

export interface SemanticSearchHit extends VideoSummary {
  match: SemanticMatch
}

export interface SemanticSearchResponse {
  items: SemanticSearchHit[]
  total: number
  index: SemanticIndexStatus
}

export interface SemanticSyncRequest {
  rebuild: boolean
}

export interface KnowledgeSource {
  sourceId: string
  videoId: number
  platformVideoId: string
  creatorSecUid: string
  creatorName: string | null
  title: string
  publishedAt: string | null
  sourceType: 'transcript' | 'analysis' | string
  start: number | null
  end: number | null
  segmentIndex: number | null
  segmentCount: number
  text: string
  score: number
}

export interface AskRequest {
  question: string
  creatorSecUid?: string
  tag?: string
  maxSources?: number
  thinking: boolean
}

export interface AskResponse {
  answer: string
  insufficientEvidence: boolean
  sources: KnowledgeSource[]
  model: string | null
  thinking: boolean
}

export interface ProcessingJob {
  id: number
  videoId: number | null
  jobType: string
  status: JobStatus
  retryCount: number
  payload: Record<string, unknown>
  result: Record<string, unknown> | null
  errorMessage: string | null
  createdAt: string
  updatedAt: string
  startedAt: string | null
  finishedAt: string | null
}

export interface JobListResponse {
  items: ProcessingJob[]
  total: number
}

export interface VideoFilters {
  q?: string
  creator?: string
  status?: string
  tag?: string
  limit?: number
  offset?: number
}

export interface JobFilters {
  status?: JobStatus
  jobType?: string
  videoId?: number
  limit?: number
}

export interface PipelineRequest {
  scan: boolean
  maxTasks?: number
}

export interface VideoProcessRequest {
  stage: VideoProcessStage
  continueToDone: boolean
}

export interface BatchVideoProcessRequest extends VideoProcessRequest {
  videoIds: number[]
}

export interface TranscriptUpdateRequest {
  transcript: string
}

export interface AnalysisUpdateRequest {
  summary: string
  tags: string[]
  keyPoints: string[]
}
