import type {
  AnalysisUpdateRequest,
  AskRequest,
  AskResponse,
  BatchVideoProcessRequest,
  CreatorDetailResponse,
  CreatorListResponse,
  DashboardResponse,
  JobFilters,
  JobListResponse,
  PipelineRequest,
  ProcessingJob,
  ReferenceAsset,
  ReferenceAssetCreateRequest,
  ReferenceAssetListResponse,
  SearchResponse,
  SemanticIndexStatus,
  SemanticSearchResponse,
  SemanticSyncRequest,
  TagListResponse,
  TopicAssetListResponse,
  TopicAssetMapRequest,
  TopicDetailResponse,
  TopicHistoryResponse,
  TopicAliasCreateRequest,
  TopicMergeResponse,
  TopicRadarFilters,
  TopicRadarResponse,
  TopicReviewFilters,
  TopicReviewItem,
  TopicReviewListResponse,
  TopicUpdateRequest,
  TranscriptUpdateRequest,
  VideoDetail,
  VideoFilters,
  VideoListResponse,
  VideoProcessRequest,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
}

function queryString(values: Record<string, string | number | boolean | undefined>): string {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      params.set(key, String(value))
    }
  })
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) message = payload.detail
    } catch {
      // Keep the HTTP fallback message when the response is not JSON.
    }
    throw new ApiError(response.status, message)
  }

  return (await response.json()) as T
}

async function getVideo(id: number): Promise<VideoDetail> {
  const video = await request<VideoDetail>(`/api/videos/${id}`)
  return {
    ...video,
    audioUrl: video.audioUrl ? apiUrl(video.audioUrl) : null,
  }
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  dashboard: () => request<DashboardResponse>('/api/dashboard'),

  topicRadar: (filters: TopicRadarFilters = {}) =>
    request<TopicRadarResponse>(
      `/api/intelligence/topics${queryString({
        windowDays: filters.windowDays ?? 7,
        status: filters.status ?? 'all',
        type: filters.topicType,
        trend: filters.trend ?? 'all',
        limit: filters.limit ?? 100,
      })}`,
    ),

  topic: (id: number, windowDays: 7 | 30 = 30, opinionLimit = 50) =>
    request<TopicDetailResponse>(
      `/api/intelligence/topics/${id}${queryString({ windowDays, opinionLimit })}`,
    ),

  topicHistory: (id: number, creator?: string, limit = 100, offset = 0) =>
    request<TopicHistoryResponse>(
      `/api/intelligence/topics/${id}/history${queryString({ creator, limit, offset })}`,
    ),

  referenceAssets: (type?: string, q?: string, limit = 100, offset = 0) =>
    request<ReferenceAssetListResponse>(
      `/api/intelligence/assets${queryString({ type, q, limit, offset })}`,
    ),

  createReferenceAsset: (payload: ReferenceAssetCreateRequest) =>
    request<ReferenceAsset>('/api/intelligence/assets', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  topicAssets: (topicId: number) =>
    request<TopicAssetListResponse>(`/api/intelligence/topics/${topicId}/assets`),

  mapTopicAsset: (topicId: number, payload: TopicAssetMapRequest) =>
    request<TopicAssetListResponse>(`/api/intelligence/topics/${topicId}/assets`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  removeTopicAsset: (topicId: number, mappingId: number) =>
    request<TopicAssetListResponse>(
      `/api/intelligence/topics/${topicId}/assets/${mappingId}/remove`,
      { method: 'POST' },
    ),

  topicReview: (filters: TopicReviewFilters = {}) =>
    request<TopicReviewListResponse>(
      `/api/intelligence/topic-review${queryString({
        status: filters.status ?? 'pending',
        type: filters.topicType,
        q: filters.q,
        limit: filters.limit ?? 100,
        offset: filters.offset ?? 0,
      })}`,
    ),

  updateTopic: (id: number, payload: TopicUpdateRequest) =>
    request<TopicReviewItem>(`/api/intelligence/topics/${id}/review`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  addTopicAlias: (id: number, payload: TopicAliasCreateRequest) =>
    request<TopicReviewItem>(`/api/intelligence/topics/${id}/aliases`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  mergeTopic: (sourceId: number, targetTopicId: number) =>
    request<TopicMergeResponse>(`/api/intelligence/topics/${sourceId}/merge`, {
      method: 'POST',
      body: JSON.stringify({ targetTopicId }),
    }),

  creators: (q?: string, limit = 100) =>
    request<CreatorListResponse>(`/api/creators${queryString({ q, limit })}`),

  creator: (secUid: string, limit = 100) =>
    request<CreatorDetailResponse>(
      `/api/creators/${encodeURIComponent(secUid)}${queryString({ limit })}`,
    ),

  videos: (filters: VideoFilters = {}) =>
    request<VideoListResponse>(
      `/api/videos${queryString({
        q: filters.q,
        creator: filters.creator,
        status: filters.status,
        tag: filters.tag,
        limit: filters.limit ?? 50,
        offset: filters.offset ?? 0,
      })}`,
    ),

  video: getVideo,

  updateTranscript: (id: number, payload: TranscriptUpdateRequest) =>
    request<VideoDetail>(`/api/videos/${id}/transcript`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }).then((video) => ({
      ...video,
      audioUrl: video.audioUrl ? apiUrl(video.audioUrl) : null,
    })),

  updateAnalysis: (id: number, payload: AnalysisUpdateRequest) =>
    request<VideoDetail>(`/api/videos/${id}/analysis`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }).then((video) => ({
      ...video,
      audioUrl: video.audioUrl ? apiUrl(video.audioUrl) : null,
    })),

  videoMarkdownExportUrl: (id: number) => apiUrl(`/api/videos/${id}/export/markdown`),
  videoJsonExportUrl: (id: number) => apiUrl(`/api/videos/${id}/export/json`),

  tags: (creator?: string, limit = 100) =>
    request<TagListResponse>(`/api/tags${queryString({ creator, limit })}`),

  search: (q: string, creator?: string, tag?: string, limit = 50) =>
    request<SearchResponse>(`/api/search${queryString({ q, creator, tag, limit })}`),

  semanticStatus: () => request<SemanticIndexStatus>('/api/semantic/status'),

  semanticSearch: (q: string, creator?: string, tag?: string, limit = 50) =>
    request<SemanticSearchResponse>(
      `/api/semantic/search${queryString({ q, creator, tag, limit })}`,
    ),

  syncSemanticIndex: (payload: SemanticSyncRequest) =>
    request<ProcessingJob>('/api/semantic/actions/sync', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  ask: (payload: AskRequest) =>
    request<AskResponse>('/api/ask', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  jobs: (filters: JobFilters = {}) =>
    request<JobListResponse>(
      `/api/jobs${queryString({
        status: filters.status,
        job_type: filters.jobType,
        video_id: filters.videoId,
        limit: filters.limit ?? 100,
      })}`,
    ),

  job: (id: number) => request<ProcessingJob>(`/api/jobs/${id}`),

  retryJob: (id: number) =>
    request<ProcessingJob>(`/api/jobs/${id}/actions/retry`, {
      method: 'POST',
    }),

  scan: (enqueue = true) =>
    request<ProcessingJob>('/api/actions/scan', {
      method: 'POST',
      body: JSON.stringify({ enqueue }),
    }),

  pipeline: (payload: PipelineRequest) =>
    request<ProcessingJob>('/api/actions/pipeline', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  processVideo: (id: number, payload: VideoProcessRequest) =>
    request<ProcessingJob>(`/api/videos/${id}/actions/process`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  processVideos: (payload: BatchVideoProcessRequest) =>
    request<ProcessingJob>('/api/videos/actions/batch-process', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safe / 60)
  const remaining = safe % 60
  return `${minutes}:${remaining.toString().padStart(2, '0')}`
}

export function formatBytes(value: number | null | undefined): string {
  if (!value) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}
