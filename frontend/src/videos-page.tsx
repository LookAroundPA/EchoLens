import { type FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
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
import type { VideoProcessStage } from './types'
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

const batchActionLabels: Record<VideoProcessStage, string> = {
  current: '继续处理',
  audio: '重新提取音频',
  transcription: '重新转写',
  analysis: '重新分析',
}

function confirmationMessage(stage: VideoProcessStage, count: number): string {
  if (stage === 'transcription') {
    return `将重新转写 ${count} 个视频，并重新生成后续分析结果。确认继续？`
  }
  if (stage === 'analysis') {
    return `将重新分析 ${count} 个视频，并替换现有分析结果。确认继续？`
  }
  return `将根据当前状态继续处理 ${count} 个视频直到完成。确认继续？`
}

export function VideosPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [status, setStatus] = useState(params.get('status') ?? '')
  const [tag, setTag] = useState(params.get('tag') ?? '')
  const [creator, setCreator] = useState(params.get('creator') ?? '')
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set())
  const offset = Number(params.get('offset') ?? 0)
  const limit = 24
  const active = {
    q: params.get('q') ?? undefined,
    creator: params.get('creator') ?? undefined,
    status: params.get('status') ?? undefined,
    tag: params.get('tag') ?? undefined,
    limit,
    offset,
  }
  const selectionScope = [
    active.q ?? '',
    active.creator ?? '',
    active.status ?? '',
    active.tag ?? '',
    String(offset),
  ].join('\u0000')

  const videos = useQuery({ queryKey: ['videos', active], queryFn: () => api.videos(active) })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => api.tags(undefined, 100) })
  const creators = useQuery({
    queryKey: ['creators', 'video-filter'],
    queryFn: () => api.creators(undefined, 500),
  })
  const batch = useMutation({
    mutationFn: ({
      videoIds,
      stage,
    }: {
      videoIds: number[]
      stage: VideoProcessStage
    }) => api.processVideos({ videoIds, stage, continueToDone: true }),
    onSuccess: (job) => {
      setSelectedIds(new Set())
      navigate(`/jobs?focus=${job.id}`)
    },
  })

  useEffect(() => {
    setSelectedIds(new Set())
    batch.reset()
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
  }

  function togglePage() {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (allPageSelected) pageIds.forEach((videoId) => next.delete(videoId))
      else pageIds.forEach((videoId) => next.add(videoId))
      return next
    })
  }

  function startBatch(stage: VideoProcessStage) {
    const videoIds = Array.from(selectedIds)
    if (!videoIds.length) return
    if (!window.confirm(confirmationMessage(stage, videoIds.length))) return
    batch.mutate({ videoIds, stage })
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
      {videos.isError ? <ErrorState error={videos.error} retry={() => { void videos.refetch() }} /> : null}
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
                    disabled={!selectedIds.size || batch.isPending}
                    onClick={() => startBatch('current')}
                  >
                    {batch.isPending ? '正在提交…' : `批量${batchActionLabels.current}`}
                  </button>
                  <button
                    className="button button-secondary"
                    disabled={!selectedIds.size || batch.isPending}
                    onClick={() => startBatch('transcription')}
                  >
                    批量{batchActionLabels.transcription}
                  </button>
                  <button
                    className="button button-primary"
                    disabled={!selectedIds.size || batch.isPending}
                    onClick={() => startBatch('analysis')}
                  >
                    批量{batchActionLabels.analysis}
                  </button>
                </div>
              </div>
              <InlineError error={batch.error} />
            </Panel>
          ) : null}

          <div className="result-line">
            <strong>{videos.data.total}</strong> 条结果
            {selectedIds.size ? <span> · 当前页已选择 {selectedIds.size} 条</span> : null}
          </div>
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
