import { type FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from './api'
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingState,
  PageHeader,
  Panel,
  VideoCard,
} from './components'
import type { ProcessingJob, VideoProcessStage } from './types'
import './videos-page.css'

const videoStatuses = [
  '',
  'pending',
  'queued',
  'processing',
  'audio_done',
  'transcribing',
  'transcribed',
  'analyzing',
  'done',
  'transcription_failed',
  'analysis_failed',
]

type BatchFeedback = {
  submitted: number
  failedVideoIds: number[]
}

export function VideosPage() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [status, setStatus] = useState(params.get('status') ?? '')
  const [tag, setTag] = useState(params.get('tag') ?? '')
  const [creator, setCreator] = useState(params.get('creator') ?? '')
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set())
  const [batchFeedback, setBatchFeedback] = useState<BatchFeedback | null>(null)
  const offset = Number(params.get('offset') ?? 0)
  const limit = 24
  const selectionScope = params.toString()
  const active = {
    q: params.get('q') ?? undefined,
    creator: params.get('creator') ?? undefined,
    status: params.get('status') ?? undefined,
    tag: params.get('tag') ?? undefined,
    limit,
    offset,
  }
  const videos = useQuery({ queryKey: ['videos', active], queryFn: () => api.videos(active) })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => api.tags(undefined, 100) })
  const creators = useQuery({
    queryKey: ['creators', 'video-filter'],
    queryFn: () => api.creators(undefined, 500),
  })
  const batchProcess = useMutation({
    mutationFn: async (stage: VideoProcessStage): Promise<BatchFeedback> => {
      const videoIds = Array.from(selectedIds)
      const results = await Promise.allSettled(
        videoIds.map((videoId) => api.processVideo(videoId, { stage, continueToDone: true })),
      )
      const jobs: ProcessingJob[] = []
      const failedVideoIds: number[] = []
      let firstError: unknown = null

      results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          jobs.push(result.value)
        } else {
          failedVideoIds.push(videoIds[index])
          firstError ??= result.reason
        }
      })

      if (!jobs.length) {
        throw firstError instanceof Error ? firstError : new Error('批量任务提交失败')
      }

      return { submitted: jobs.length, failedVideoIds }
    },
    onSuccess: (result) => {
      setBatchFeedback(result)
      setSelectedIds(new Set())
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  useEffect(() => {
    setSelectedIds(new Set())
    setBatchFeedback(null)
    batchProcess.reset()
  }, [selectionScope])

  const pageIds = videos.data?.items.map((video) => video.id) ?? []
  const allPageSelected = pageIds.length > 0 && pageIds.every((videoId) => selectedIds.has(videoId))

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    if (q.trim()) next.set('q', q.trim())
    if (status) next.set('status', status)
    if (tag) next.set('tag', tag)
    if (creator) next.set('creator', creator)
    setParams(next)
  }

  function toggleVideo(videoId: number) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(videoId)) next.delete(videoId)
      else next.add(videoId)
      return next
    })
    setBatchFeedback(null)
  }

  function togglePage() {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (allPageSelected) pageIds.forEach((videoId) => next.delete(videoId))
      else pageIds.forEach((videoId) => next.add(videoId))
      return next
    })
    setBatchFeedback(null)
  }

  function submitBatch(stage: VideoProcessStage, actionLabel: string, consequence: string) {
    const count = selectedIds.size
    if (!count) return
    const confirmed = window.confirm(
      `确认对 ${count} 个视频执行“${actionLabel}”吗？\n\n${consequence}`,
    )
    if (!confirmed) return
    setBatchFeedback(null)
    batchProcess.mutate(stage)
  }

  return (
    <>
      <PageHeader
        eyebrow="内容库"
        title="视频"
        description="浏览和筛选内容，选择当前页视频后可批量继续处理、重新转写或重新分析。"
      />
      <Panel className="filter-panel">
        <form className="filter-bar filter-bar-wrap" onSubmit={submit}>
          <label className="field grow">
            <span>关键词</span>
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="描述、摘要、观点或转写"
            />
          </label>
          <label className="field">
            <span>创作者</span>
            <select value={creator} onChange={(event) => setCreator(event.target.value)}>
              <option value="">全部创作者</option>
              {creators.data?.items.map((item) => (
                <option key={item.secUid} value={item.secUid}>{item.name || item.secUid}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {videoStatuses.map((item) => (
                <option key={item || 'all'} value={item}>{item || '全部状态'}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>标签</span>
            <select value={tag} onChange={(event) => setTag(event.target.value)}>
              <option value="">全部标签</option>
              {tags.data?.items.map((item) => (
                <option key={item.tag} value={item.tag}>{item.tag} ({item.count})</option>
              ))}
            </select>
          </label>
          <button className="button button-primary" type="submit">筛选</button>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => {
              setQ('')
              setStatus('')
              setTag('')
              setCreator('')
              setParams({})
            }}
          >
            清空
          </button>
        </form>
      </Panel>

      {videos.isLoading ? <LoadingState /> : null}
      {videos.isError ? <ErrorState error={videos.error} retry={() => videos.refetch()} /> : null}
      {videos.data ? (
        <div className="page-stack">
          {videos.data.items.length ? (
            <Panel className="batch-panel">
              <div className="batch-toolbar">
                <label className="check-field batch-select-all">
                  <input type="checkbox" checked={allPageSelected} onChange={togglePage} />
                  选择本页
                </label>
                <strong>已选择 {selectedIds.size} 个视频</strong>
                <div className="batch-actions">
                  <button
                    className="button button-secondary"
                    disabled={!selectedIds.size || batchProcess.isPending}
                    onClick={() => submitBatch(
                      'current',
                      '继续处理',
                      '系统会根据每个视频的当前状态继续执行，并尽可能处理到 done。',
                    )}
                  >
                    批量继续处理
                  </button>
                  <button
                    className="button button-secondary"
                    disabled={!selectedIds.size || batchProcess.isPending}
                    onClick={() => submitBatch(
                      'transcription',
                      '重新转写',
                      '现有转写和分析结果会被清除，然后重新转写并继续分析。',
                    )}
                  >
                    批量重新转写
                  </button>
                  <button
                    className="button button-primary"
                    disabled={!selectedIds.size || batchProcess.isPending}
                    onClick={() => submitBatch(
                      'analysis',
                      '重新分析',
                      '现有分析结果会被清除，并基于当前转写重新调用 DeepSeek。',
                    )}
                  >
                    {batchProcess.isPending ? '正在提交…' : '批量重新分析'}
                  </button>
                </div>
              </div>
              <InlineError error={batchProcess.error} />
              {batchFeedback ? (
                <div className={batchFeedback.failedVideoIds.length ? 'batch-feedback batch-feedback-warning' : 'batch-feedback'}>
                  <span>
                    已创建 {batchFeedback.submitted} 个处理任务
                    {batchFeedback.failedVideoIds.length
                      ? `，${batchFeedback.failedVideoIds.length} 个视频提交失败：${batchFeedback.failedVideoIds.join('、')}`
                      : '。'}
                  </span>
                  <Link className="text-link" to="/jobs?type=video_process">打开任务中心 →</Link>
                </div>
              ) : null}
            </Panel>
          ) : null}

          <div className="result-line"><strong>{videos.data.total}</strong> 条结果</div>
          {videos.data.items.length ? (
            <div className="video-grid video-grid-selectable">
              {videos.data.items.map((video) => (
                <article
                  className={`selectable-video${selectedIds.has(video.id) ? ' is-selected' : ''}`}
                  key={video.id}
                >
                  <label className="video-selection-control">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(video.id)}
                      onChange={() => toggleVideo(video.id)}
                    />
                    <span>选择视频 #{video.id}</span>
                  </label>
                  <VideoCard video={video} />
                </article>
              ))}
            </div>
          ) : <EmptyState title="没有匹配内容" description="调整筛选条件或先运行处理流程。" />}
          <div className="pagination">
            <button
              className="button button-secondary"
              disabled={offset <= 0}
              onClick={() => {
                const next = new URLSearchParams(params)
                next.set('offset', String(Math.max(0, offset - limit)))
                setParams(next)
              }}
            >
              上一页
            </button>
            <span>第 {Math.floor(offset / limit) + 1} 页</span>
            <button
              className="button button-secondary"
              disabled={offset + limit >= videos.data.total}
              onClick={() => {
                const next = new URLSearchParams(params)
                next.set('offset', String(offset + limit))
                setParams(next)
              }}
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
