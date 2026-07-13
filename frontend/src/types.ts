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

export interface VideoDetail extends VideoSummary {
  transcript: string | null
  segments: TranscriptSegment[]
  language: string | null
  audioSize: number | null
  audioUrl: string | null
  transcriptionModel: string | null
  analysisModel: string | null
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
}

export interface VideoListResponse {
  items: VideoSummary[]
  total: number
}

export interface TagListResponse {
  items: TagCount[]
}

export interface SearchResponse {
  items: VideoSummary[]
  total: number
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
