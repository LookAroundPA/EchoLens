import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from './api'
import { JobBadge } from './components'
import { JobsPage as BaseJobsPage } from './jobs-page'
import type { ProcessingJob } from './types'
import './jobs-page-progress.css'

type ProgressData = {
  unit: string
  completed: number
  total: number
  percent: number
  currentStage: string | null
  currentVideoId: number | null
}

const stageLabels: Record<string, string> = {
  scan: '扫描与入队',
  audio: '音频提取',
  transcription: '语音转写',
  analysis: '内容分析',
  semantic: '本地语义索引',
  current: '根据当前状态继续',
}

function progressFromJob(job: ProcessingJob): ProgressData | null {
  const raw = job.result?.progress
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const value = raw as Record<string, unknown>
  const completed = Number(value.completed)
  const total = Number(value.total)
  const percent = Number(value.percent)
  if (![completed, total, percent].every(Number.isFinite)) return null
  const currentVideoId = value.currentVideoId !== null
    && value.currentVideoId !== undefined
    && Number.isFinite(Number(value.currentVideoId))
    ? Number(value.currentVideoId)
    : null
  return {
    unit: typeof value.unit === 'string' ? value.unit : 'stage',
    completed,
    total,
    percent: Math.max(0, Math.min(100, percent)),
    currentStage: typeof value.currentStage === 'string' ? value.currentStage : null,
    currentVideoId,
  }
}

function progressDescription(job: ProcessingJob, progress: ProgressData | null): string {
  if (job.status === 'queued') return '任务正在等待当前运行任务完成。'
  if (!progress) {
    return job.jobType === 'semantic_index'
      ? '正在检查内容变化并生成本地语义向量。首次运行可能需要下载嵌入模型。'
      : '任务已经开始，正在等待第一个阶段状态。'
  }
  if (job.status === 'succeeded') {
    return progress.unit === 'video'
      ? `已处理 ${progress.total} 个视频。`
      : `已完成 ${progress.total} 个处理阶段。`
  }

  const stage = progress.currentStage
    ? stageLabels[progress.currentStage] ?? progress.currentStage
    : '准备下一阶段'
  if (progress.unit === 'video') {
    const currentVideo = progress.currentVideoId ? ` · 当前视频 #${progress.currentVideoId}` : ''
    return `已处理 ${progress.completed} / ${progress.total} 个视频${currentVideo} · ${stage}`
  }
  return `已完成 ${progress.completed} / ${progress.total} 个阶段 · 当前：${stage}`
}

function JobProgressCard({ job }: { job: ProcessingJob }) {
  const progress = progressFromJob(job)
  const visible = job.status === 'queued' || job.status === 'running' || progress !== null
  if (!visible) return null

  const percent = job.status === 'queued' ? 0 : progress?.percent ?? 0
  return (
    <aside className="job-progress-card" aria-live="polite">
      <div className="job-progress-heading">
        <div>
          <span>任务 #{job.id}</span>
          <strong>阶段进度</strong>
        </div>
        <JobBadge status={job.status} />
      </div>
      <div
        className="job-progress-track"
        role="progressbar"
        aria-label={`任务 #${job.id} 阶段进度`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="job-progress-meta">
        <strong>{Math.round(percent)}%</strong>
        <p>{progressDescription(job, progress)}</p>
      </div>
      <small>此百分比仅表示已完成的阶段或视频数量，不代表 Whisper、DeepSeek 或嵌入模型内部耗时。</small>
    </aside>
  )
}

export function JobsPage() {
  const [params] = useSearchParams()
  const focusId = Number(params.get('focus'))
  const focusedJob = useQuery({
    queryKey: ['job', focusId],
    queryFn: () => api.job(focusId),
    enabled: Number.isFinite(focusId) && focusId > 0,
  })

  return (
    <>
      <BaseJobsPage />
      {focusedJob.data ? <JobProgressCard job={focusedJob.data} /> : null}
    </>
  )
}
