import { type FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatDate } from './api'
import {
  EmptyState,
  ErrorState,
  InlineError,
  JobBadge,
  LoadingState,
  PageHeader,
  Panel,
} from './components'
import type { JobStatus, ProcessingJob, VideoProcessStage } from './types'
import './jobs-page-failures.css'

const jobStatuses: Array<JobStatus | ''> = ['', 'queued', 'running', 'succeeded', 'failed']
const jobTypes = ['', 'scan', 'pipeline', 'video_process', 'video_batch']

const jobTypeLabels: Record<string, string> = {
  scan: '扫描内容源',
  pipeline: '完整处理流程',
  video_process: '单视频处理',
  video_batch: '批量视频处理',
}

const metricLabels: Record<string, string> = {
  discovered: '发现',
  skipped: '跳过',
  inserted: '新增入库',
  queued: '已入队',
  skippedExisting: '已存在',
  processed: '已处理',
  total: '视频总数',
  completed: '已完成',
  failed: '失败',
  enqueue: '入队',
  finalStatus: '最终状态',
  requestedStage: '请求阶段',
  resolvedStage: '实际阶段',
  continueToDone: '继续到完成',
}

type BatchFailureItem = {
  videoId: number
  error: string
}

type BatchRetryPayload = {
  videoIds: number[]
  stage: VideoProcessStage
  continueToDone: boolean
}

function displayMetric(value: unknown): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function metricEntries(value: unknown): Array<[string, unknown]> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  return Object.entries(value as Record<string, unknown>).filter(
    ([, item]) => typeof item !== 'object' || item === null,
  )
}

function jobStageEntries(job: ProcessingJob): Array<[string, unknown]> {
  const result = job.result
  if (!result) return []
  if (job.jobType === 'scan') return [['scan', result]]
  if (job.jobType === 'pipeline') {
    return ['scan', 'audio', 'transcription', 'analysis']
      .filter((key) => key in result)
      .map((key) => [key, result[key]])
  }
  if (job.jobType === 'video_process') {
    const stages = result.stages
    if (!stages || typeof stages !== 'object' || Array.isArray(stages)) return []
    return Object.entries(stages as Record<string, unknown>)
  }
  return []
}

function stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    scan: '扫描与入队',
    current: '根据当前状态继续',
    audio: '音频提取',
    transcription: '语音转写',
    analysis: '内容分析',
  }
  return labels[stage] ?? stage
}

function jobTarget(job: ProcessingJob): string {
  if (job.videoId) return `视频 #${job.videoId}`
  const videoIds = job.payload.videoIds
  if (job.jobType === 'video_batch' && Array.isArray(videoIds)) {
    return `${videoIds.length} 个视频`
  }
  return '全局任务'
}

function isVideoProcessStage(value: unknown): value is VideoProcessStage {
  return value === 'current'
    || value === 'audio'
    || value === 'transcription'
    || value === 'analysis'
}

function batchFailureItems(job: ProcessingJob): BatchFailureItem[] {
  if (job.jobType !== 'video_batch' || !job.result) return []
  const items = job.result.items
  if (!Array.isArray(items)) return []

  const failures: BatchFailureItem[] = []
  for (const rawItem of items) {
    if (!rawItem || typeof rawItem !== 'object' || Array.isArray(rawItem)) continue
    const item = rawItem as Record<string, unknown>
    if (item.succeeded !== false) continue
    const videoId = Number(item.videoId)
    if (!Number.isInteger(videoId) || videoId < 1) continue
    failures.push({
      videoId,
      error: typeof item.error === 'string' && item.error.trim()
        ? item.error.trim()
        : '未提供错误原因',
    })
  }
  return failures
}

function batchRetryPayload(job: ProcessingJob): BatchRetryPayload | null {
  const failures = batchFailureItems(job)
  if (!failures.length) return null

  const rawStage = job.payload.stage ?? job.result?.requestedStage
  const stage = isVideoProcessStage(rawStage) ? rawStage : 'current'
  const continueToDone = typeof job.payload.continueToDone === 'boolean'
    ? job.payload.continueToDone
    : true

  return {
    videoIds: failures.map((item) => item.videoId),
    stage,
    continueToDone,
  }
}

export function JobsPage() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const focusId = Number(params.get('focus'))
  const currentStatus = params.get('status') ?? ''
  const currentType = params.get('type') ?? ''
  const [status, setStatus] = useState(currentStatus)
  const [jobType, setJobType] = useState(currentType)

  const jobs = useQuery({
    queryKey: ['jobs', currentStatus, currentType],
    queryFn: () => api.jobs({
      status: currentStatus ? currentStatus as JobStatus : undefined,
      jobType: currentType || undefined,
      limit: 100,
    }),
    refetchInterval: (query) => query.state.data?.items.some(
      (job) => job.status === 'queued' || job.status === 'running',
    ) ? 2000 : 10_000,
  })

  const focusedJob = useQuery({
    queryKey: ['job', focusId],
    queryFn: () => api.job(focusId),
    enabled: Number.isFinite(focusId) && focusId > 0,
    refetchInterval: (query) => {
      const current = query.state.data
      return current?.status === 'queued' || current?.status === 'running' ? 2000 : false
    },
  })

  function focusCreatedJob(job: ProcessingJob) {
    queryClient.setQueryData(['job', job.id], job)
    void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    const next = new URLSearchParams(params)
    next.set('focus', String(job.id))
    setParams(next)
  }

  const retryJob = useMutation({
    mutationFn: (jobId: number) => api.retryJob(jobId),
    onSuccess: focusCreatedJob,
  })

  const retryBatchFailures = useMutation({
    mutationFn: (payload: BatchRetryPayload) => api.processVideos(payload),
    onSuccess: focusCreatedJob,
  })

  useEffect(() => {
    if (focusedJob.data?.status !== 'succeeded') return
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    void queryClient.invalidateQueries({ queryKey: ['videos'] })
    void queryClient.invalidateQueries({ queryKey: ['video'] })
    void queryClient.invalidateQueries({ queryKey: ['creators'] })
    void queryClient.invalidateQueries({ queryKey: ['creator'] })
    void queryClient.invalidateQueries({ queryKey: ['tags'] })
    void queryClient.invalidateQueries({ queryKey: ['search'] })
  }, [focusedJob.data?.id, focusedJob.data?.status, queryClient])

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams(params)
    next.delete('focus')
    if (status) next.set('status', status); else next.delete('status')
    if (jobType) next.set('type', jobType); else next.delete('type')
    setParams(next)
  }

  function closeFocusedJob() {
    const next = new URLSearchParams(params)
    next.delete('focus')
    setParams(next)
  }

  function retryFocusedBatchFailures() {
    const job = focusedJob.data
    if (!job) return
    const payload = batchRetryPayload(job)
    if (!payload) return
    const confirmed = window.confirm(
      `将按原任务阶段“${stageLabel(payload.stage)}”重新处理 ${payload.videoIds.length} 个失败视频。\n\n原任务和错误记录会保留，确认继续？`,
    )
    if (!confirmed) return
    retryBatchFailures.mutate(payload)
  }

  return (
    <>
      <PageHeader
        eyebrow="运行中心"
        title="处理任务"
        description="查看扫描、完整 pipeline、单视频和批量处理的实时状态；失败任务或批量失败项可直接重新执行。"
        actions={(
          <button
            className="button button-secondary"
            onClick={() => {
              void jobs.refetch()
              if (Number.isFinite(focusId) && focusId > 0) void focusedJob.refetch()
            }}
          >
            刷新
          </button>
        )}
      />
      <Panel className="filter-panel">
        <form className="filter-bar" onSubmit={applyFilters}>
          <label className="field">
            <span>任务状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {jobStatuses.map((item) => (
                <option key={item || 'all'} value={item}>{item || '全部状态'}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>任务类型</span>
            <select value={jobType} onChange={(event) => setJobType(event.target.value)}>
              {jobTypes.map((item) => (
                <option key={item || 'all'} value={item}>
                  {item ? jobTypeLabels[item] : '全部类型'}
                </option>
              ))}
            </select>
          </label>
          <button className="button button-primary">筛选</button>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => {
              setStatus('')
              setJobType('')
              setParams({})
            }}
          >
            清空
          </button>
        </form>
      </Panel>

      {focusedJob.isLoading ? <LoadingState label="正在读取任务详情…" /> : null}
      {focusedJob.isError ? (
        <ErrorState error={focusedJob.error} retry={() => { void focusedJob.refetch() }} />
      ) : null}
      {focusedJob.data ? (
        <JobDetail
          job={focusedJob.data}
          close={closeFocusedJob}
          retry={() => retryJob.mutate(focusId)}
          retryFailedItems={retryFocusedBatchFailures}
          isRetrying={retryJob.isPending}
          isRetryingFailedItems={retryBatchFailures.isPending}
        />
      ) : null}
      <InlineError error={retryJob.error || retryBatchFailures.error} />

      {jobs.isLoading ? <LoadingState /> : null}
      {jobs.isError ? <ErrorState error={jobs.error} retry={() => { void jobs.refetch() }} /> : null}
      {jobs.data ? (
        <Panel title={`任务列表 · ${jobs.data.total}`}>
          {jobs.data.items.length ? (
            <div className="job-list">
              {jobs.data.items.map((job) => (
                <button
                  className={`job-row${job.id === focusId ? ' is-selected' : ''}`}
                  key={job.id}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('focus', String(job.id))
                    setParams(next)
                  }}
                >
                  <span className="job-id">#{job.id}</span>
                  <span>
                    <strong>{jobTypeLabels[job.jobType] ?? job.jobType}</strong>
                    <small>{formatDate(job.createdAt)}</small>
                  </span>
                  <span>{jobTarget(job)}</span>
                  <JobBadge status={job.status} />
                </button>
              ))}
            </div>
          ) : <EmptyState title="没有匹配任务" />}
        </Panel>
      ) : null}
    </>
  )
}

function JobDetail({
  job,
  close,
  retry,
  retryFailedItems,
  isRetrying,
  isRetryingFailedItems,
}: {
  job: ProcessingJob
  close: () => void
  retry: () => void
  retryFailedItems: () => void
  isRetrying: boolean
  isRetryingFailedItems: boolean
}) {
  const stages = jobStageEntries(job)
  const failedItems = batchFailureItems(job)
  const resultMetrics = job.result
    ? metricEntries(job.result).filter(([key]) => key !== 'stages')
    : []
  const retryLabel = job.retryCount > 0 ? ` · 第 ${job.retryCount} 次重试` : ''

  return (
    <Panel
      className="job-detail"
      title={`任务 #${job.id} · ${jobTypeLabels[job.jobType] ?? job.jobType}${retryLabel}`}
      action={(
        <div className="page-actions">
          {job.status === 'succeeded' && failedItems.length ? (
            <button
              className="button button-primary"
              onClick={retryFailedItems}
              disabled={isRetryingFailedItems}
            >
              {isRetryingFailedItems
                ? '正在提交…'
                : `重试 ${failedItems.length} 个失败项`}
            </button>
          ) : null}
          {job.status === 'failed' ? (
            <button
              className="button button-primary"
              onClick={retry}
              disabled={isRetrying}
            >
              {isRetrying ? '正在提交…' : '重试失败任务'}
            </button>
          ) : null}
          <button className="icon-button" onClick={close} aria-label="关闭">×</button>
        </div>
      )}
    >
      <div className="job-detail-grid">
        <div><span>状态</span><JobBadge status={job.status} /></div>
        <div><span>创建时间</span><strong>{formatDate(job.createdAt)}</strong></div>
        <div><span>开始时间</span><strong>{formatDate(job.startedAt)}</strong></div>
        <div><span>完成时间</span><strong>{formatDate(job.finishedAt)}</strong></div>
      </div>
      {job.videoId ? (
        <Link className="job-video-link" to={`/videos/${job.videoId}`}>
          打开关联视频 #{job.videoId} →
        </Link>
      ) : null}
      {job.errorMessage ? <p className="inline-error">{job.errorMessage}</p> : null}
      {job.status === 'failed' ? (
        <p className="muted">重试会保留当前失败记录，并创建一个新的排队任务。</p>
      ) : null}
      {failedItems.length ? (
        <section className="batch-failure-section">
          <div className="batch-failure-heading">
            <div>
              <strong>批量任务中的失败项</strong>
              <p>只重试下列视频，不会重复处理本批次中已经成功的视频。</p>
            </div>
            <span>{failedItems.length}</span>
          </div>
          <div className="batch-failure-list">
            {failedItems.map((item) => (
              <article className="batch-failure-item" key={item.videoId}>
                <Link to={`/videos/${item.videoId}`}>视频 #{item.videoId}</Link>
                <p>{item.error}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {(job.status === 'queued' || job.status === 'running') ? (
        <div className="job-running-note">
          <span className="spinner" />任务正在后台执行，页面会自动刷新状态。
        </div>
      ) : null}
      {stages.length ? (
        <div className="job-stages">
          {stages.map(([stage, value]) => (
            <article className="job-stage" key={stage}>
              <div className="job-stage-header">
                <span>{stageLabel(stage)}</span><strong>已执行</strong>
              </div>
              <div className="stage-metrics">
                {metricEntries(value).map(([key, metric]) => (
                  <div key={key}>
                    <span>{metricLabels[key] ?? key}</span>
                    <strong>{displayMetric(metric)}</strong>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : null}
      {resultMetrics.length ? (
        <div className="result-metrics">
          {resultMetrics.map(([key, value]) => (
            <div key={key}>
              <span>{metricLabels[key] ?? key}</span>
              <strong>{displayMetric(value)}</strong>
            </div>
          ))}
        </div>
      ) : null}
      <details open={job.status === 'failed'}>
        <summary>原始请求与执行结果</summary>
        <div className="json-grid">
          <div><h3>Payload</h3><pre>{JSON.stringify(job.payload, null, 2)}</pre></div>
          <div><h3>Result</h3><pre>{JSON.stringify(job.result, null, 2)}</pre></div>
        </div>
      </details>
    </Panel>
  )
}
