import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, formatBytes, formatDate, formatDuration } from './api'
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingState,
  PageHeader,
  Panel,
  StatusBadge,
  TagPills,
} from './components'
import type { KeyPointEvidence, ProcessingJob, VideoDetail, VideoProcessStage } from './types'
import './video-detail-page.css'

function uniqueLines(value: string): string[] {
  return Array.from(new Set(
    value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean),
  ))
}

function hasAnalysis(item: VideoDetail): boolean {
  return Boolean(item.summary || item.tags.length || item.keyPoints.length || item.analysisModel)
}

function parseNonNegativeNumber(value: string | null): number | null {
  if (value === null || value.trim() === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}

function parseSegmentIndex(value: string | null, length: number): number | null {
  if (value === null || value.trim() === '') return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed < length ? parsed : null
}

function evidenceMap(items: KeyPointEvidence[]): Map<number, KeyPointEvidence> {
  return new Map(items.map((item) => [item.keyPointIndex, item]))
}

export function VideoDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const videoId = Number(id)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const segmentRefs = useRef<Array<HTMLButtonElement | null>>([])
  const lastAppliedDeepLink = useRef<string | null>(null)
  const [stage, setStage] = useState<VideoProcessStage>('current')
  const [continueToDone, setContinueToDone] = useState(true)
  const [editingTranscript, setEditingTranscript] = useState(false)
  const [editingAnalysis, setEditingAnalysis] = useState(false)
  const [transcriptDraft, setTranscriptDraft] = useState('')
  const [summaryDraft, setSummaryDraft] = useState('')
  const [tagsDraft, setTagsDraft] = useState('')
  const [keyPointsDraft, setKeyPointsDraft] = useState('')
  const [currentTime, setCurrentTime] = useState(0)
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null)
  const [playbackNotice, setPlaybackNotice] = useState('')
  const [copyNotice, setCopyNotice] = useState('')

  const video = useQuery({
    queryKey: ['video', videoId],
    queryFn: () => api.video(videoId),
    enabled: Number.isFinite(videoId),
  })

  useEffect(() => {
    const item = video.data
    if (!item) return
    setTranscriptDraft(item.transcript ?? '')
    setSummaryDraft(item.summary ?? '')
    setTagsDraft(item.tags.join('\n'))
    setKeyPointsDraft(item.keyPoints.join('\n'))
  }, [video.data?.id, video.data?.updatedAt])

  const currentVideo = video.data
  const sourceByKeyPoint = useMemo(
    () => evidenceMap(currentVideo?.keyPointEvidence ?? []),
    [currentVideo?.keyPointEvidence],
  )
  const timeParam = searchParams.get('t')
  const segmentParam = searchParams.get('segment')
  const transcriptDirty = editingTranscript
    && transcriptDraft !== (currentVideo?.transcript ?? '')
  const analysisDirty = editingAnalysis && currentVideo !== undefined && (
    summaryDraft !== (currentVideo.summary ?? '')
    || tagsDraft !== currentVideo.tags.join('\n')
    || keyPointsDraft !== currentVideo.keyPoints.join('\n')
  )

  useEffect(() => {
    if (!transcriptDirty && !analysisDirty) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [transcriptDirty, analysisDirty])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || audio.readyState === 0 || !currentVideo) return
    applyDeepLink()
  }, [currentVideo?.audioUrl, currentVideo?.segments, timeParam, segmentParam])

  function openJob(job: ProcessingJob) {
    navigate(`/jobs?focus=${job.id}`)
  }

  function refreshKnowledge(updated: VideoDetail) {
    queryClient.setQueryData(['video', videoId], updated)
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    void queryClient.invalidateQueries({ queryKey: ['videos'] })
    void queryClient.invalidateQueries({ queryKey: ['creators'] })
    void queryClient.invalidateQueries({ queryKey: ['creator'] })
    void queryClient.invalidateQueries({ queryKey: ['tags'] })
    void queryClient.invalidateQueries({ queryKey: ['search'] })
  }

  const process = useMutation({
    mutationFn: () => api.processVideo(videoId, { stage, continueToDone }),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ['video', videoId] })
      openJob(job)
    },
  })

  const reanalyze = useMutation({
    mutationFn: () => api.processVideo(videoId, {
      stage: 'analysis',
      continueToDone: true,
    }),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ['video', videoId] })
      openJob(job)
    },
  })

  const saveTranscript = useMutation({
    mutationFn: async ({ reanalyzeAfterSave }: { reanalyzeAfterSave: boolean }) => {
      const updated = await api.updateTranscript(videoId, { transcript: transcriptDraft })
      const job = reanalyzeAfterSave
        ? await api.processVideo(videoId, { stage: 'analysis', continueToDone: true })
        : null
      return { updated, job }
    },
    onSuccess: ({ updated, job }) => {
      refreshKnowledge(updated)
      setEditingTranscript(false)
      if (job) openJob(job)
    },
  })

  const saveAnalysis = useMutation({
    mutationFn: () => api.updateAnalysis(videoId, {
      summary: summaryDraft,
      tags: uniqueLines(tagsDraft),
      keyPoints: uniqueLines(keyPointsDraft),
    }),
    onSuccess: (updated) => {
      refreshKnowledge(updated)
      setEditingAnalysis(false)
    },
  })

  function cancelTranscriptEdit() {
    setTranscriptDraft(video.data?.transcript ?? '')
    setEditingTranscript(false)
  }

  function cancelAnalysisEdit() {
    setSummaryDraft(video.data?.summary ?? '')
    setTagsDraft(video.data?.tags.join('\n') ?? '')
    setKeyPointsDraft(video.data?.keyPoints.join('\n') ?? '')
    setEditingAnalysis(false)
  }

  function submitTranscript(reanalyzeAfterSave: boolean) {
    if (!transcriptDraft.trim()) return
    if (reanalyzeAfterSave) {
      const confirmed = window.confirm('保存转写后将立即创建重新分析任务，确认继续？')
      if (!confirmed) return
    }
    saveTranscript.mutate({ reanalyzeAfterSave })
  }

  function scrollToSegment(index: number) {
    window.requestAnimationFrame(() => {
      segmentRefs.current[index]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  function updateDeepLink(start: number, segmentIndex: number | null) {
    const next = new URLSearchParams(searchParams)
    const normalizedTime = Math.round(start * 100) / 100
    next.set('t', String(normalizedTime))
    if (segmentIndex !== null) next.set('segment', String(segmentIndex))
    else next.delete('segment')
    setSearchParams(next, { replace: true })
    return `${videoId}:${normalizedTime}:${segmentIndex ?? ''}`
  }

  function playFrom(start: number, segmentIndex: number | null, updateUrl = true) {
    const audio = audioRef.current
    if (updateUrl) lastAppliedDeepLink.current = updateDeepLink(start, segmentIndex)
    setCurrentTime(start)
    setActiveSegmentIndex(segmentIndex)
    setPlaybackNotice('')
    if (segmentIndex !== null) scrollToSegment(segmentIndex)
    if (!audio || audio.readyState === 0) return
    audio.currentTime = start
    void audio.play().catch(() => {
      setPlaybackNotice(`已定位到 ${formatDuration(start)}，浏览器阻止了自动播放，请点击播放器开始。`)
    })
  }

  function applyDeepLink() {
    const item = currentVideo
    const audio = audioRef.current
    if (!item || !audio) return
    const requestedSegment = parseSegmentIndex(segmentParam, item.segments.length)
    const requestedTime = parseNonNegativeNumber(timeParam)
    const targetTime = requestedTime ?? (
      requestedSegment !== null ? item.segments[requestedSegment]?.start ?? null : null
    )
    if (targetTime === null) return
    const targetSegment = requestedSegment ?? item.segments.findIndex(
      (segment) => targetTime >= segment.start && targetTime < segment.end,
    )
    const normalizedSegment = targetSegment >= 0 ? targetSegment : null
    const key = `${videoId}:${Math.round(targetTime * 100) / 100}:${normalizedSegment ?? ''}`
    if (lastAppliedDeepLink.current === key) return
    lastAppliedDeepLink.current = key
    playFrom(targetTime, normalizedSegment, false)
  }

  function handleTimeUpdate() {
    const audio = audioRef.current
    const item = currentVideo
    if (!audio || !item) return
    const time = audio.currentTime
    setCurrentTime(time)
    const index = item.segments.findIndex(
      (segment) => time >= segment.start && time < segment.end,
    )
    setActiveSegmentIndex(index >= 0 ? index : null)
  }

  async function copyCurrentLink() {
    const url = new URL(window.location.href)
    url.searchParams.set('t', String(Math.round(currentTime * 100) / 100))
    if (activeSegmentIndex !== null) url.searchParams.set('segment', String(activeSegmentIndex))
    else url.searchParams.delete('segment')
    try {
      await navigator.clipboard.writeText(url.toString())
      setCopyNotice('已复制时间链接')
    } catch {
      setCopyNotice('复制失败，请复制浏览器地址栏')
    }
    window.setTimeout(() => setCopyNotice(''), 2500)
  }

  if (!Number.isFinite(videoId)) return <ErrorState error={new Error('无效的视频 ID')} />
  if (video.isLoading) return <LoadingState label="正在读取视频详情…" />
  if (video.isError) return <ErrorState error={video.error} retry={() => { void video.refetch() }} />
  if (!video.data) return null

  const item = video.data
  const analysisStale = item.status === 'transcribed' && hasAnalysis(item)

  return (
    <>
      <PageHeader
        eyebrow={item.creatorName || '视频详情'}
        title={item.description || `视频 ${item.videoId}`}
        description={`平台 ID：${item.videoId} · ${formatDate(item.publishedAt)}`}
        actions={(
          <>
            <a className="button button-secondary" href={api.videoMarkdownExportUrl(videoId)}>导出 Markdown</a>
            <a className="button button-secondary" href={api.videoJsonExportUrl(videoId)}>导出 JSON</a>
            <StatusBadge status={item.status} />
          </>
        )}
      />
      {analysisStale ? (
        <div className="analysis-stale-notice">
          <strong>分析需要更新</strong>
          <span>转写已经人工修改，当前摘要、标签和关键观点仍是旧结果。可继续参考，也可重新分析。</span>
          <button
            className="button button-primary"
            onClick={() => reanalyze.mutate()}
            disabled={reanalyze.isPending}
          >
            {reanalyze.isPending ? '正在提交…' : '重新分析'}
          </button>
          <InlineError error={reanalyze.error} />
        </div>
      ) : null}
      <div className="detail-layout">
        <div className="detail-main page-stack">
          <Panel
            title="内容分析"
            description={analysisStale ? '当前显示的是修改转写前的分析结果。' : '关键观点会自动关联最接近的原始转写片段。'}
            action={!editingAnalysis ? (
              <button className="button button-secondary" onClick={() => setEditingAnalysis(true)}>编辑分析</button>
            ) : undefined}
          >
            {editingAnalysis ? (
              <div className="editor-stack">
                <label className="field">
                  <span>摘要</span>
                  <textarea
                    className="editor-textarea editor-textarea-summary"
                    value={summaryDraft}
                    onChange={(event) => setSummaryDraft(event.target.value)}
                    placeholder="输入内容摘要"
                  />
                </label>
                <label className="field">
                  <span>标签（每行一个）</span>
                  <textarea
                    className="editor-textarea editor-textarea-list"
                    value={tagsDraft}
                    onChange={(event) => setTagsDraft(event.target.value)}
                    placeholder={'人工智能\n商业\n学习方法'}
                  />
                </label>
                <label className="field">
                  <span>关键观点（每行一个）</span>
                  <textarea
                    className="editor-textarea editor-textarea-points"
                    value={keyPointsDraft}
                    onChange={(event) => setKeyPointsDraft(event.target.value)}
                    placeholder="每行填写一条关键观点"
                  />
                </label>
                <div className="editor-actions">
                  <button
                    className="button button-primary"
                    onClick={() => saveAnalysis.mutate()}
                    disabled={saveAnalysis.isPending}
                  >
                    {saveAnalysis.isPending ? '正在保存…' : '保存分析'}
                  </button>
                  <button className="button button-secondary" onClick={cancelAnalysisEdit} disabled={saveAnalysis.isPending}>取消</button>
                </div>
                <InlineError error={saveAnalysis.error} />
              </div>
            ) : (
              <div className="analysis-view">
                <div>
                  <h3>摘要</h3>
                  <p className="summary-text">{item.summary || '尚未生成摘要。'}</p>
                </div>
                <div>
                  <h3>标签</h3>
                  <TagPills tags={item.tags} />
                </div>
                <div>
                  <h3>关键观点</h3>
                  {item.keyPoints.length ? (
                    <ol className="key-points key-points-with-sources">
                      {item.keyPoints.map((point, index) => {
                        const evidence = sourceByKeyPoint.get(index)
                        return (
                          <li key={`${index}-${point}`}>
                            <p>{point}</p>
                            {evidence ? (
                              <button
                                type="button"
                                className="evidence-link"
                                onClick={() => playFrom(evidence.start, evidence.segmentIndex)}
                              >
                                <span>▶ 来源 {formatDuration(evidence.start)} – {formatDuration(evidence.end)}</span>
                                <small>{evidence.text}</small>
                              </button>
                            ) : <small className="evidence-missing">未自动匹配到明确时间片段</small>}
                          </li>
                        )
                      })}
                    </ol>
                  ) : <EmptyState title="暂无关键观点" />}
                </div>
              </div>
            )}
          </Panel>
          <Panel
            title="完整转写"
            description={item.language ? `识别语言：${item.language}` : undefined}
            action={!editingTranscript ? (
              <button className="button button-secondary" onClick={() => setEditingTranscript(true)}>编辑转写</button>
            ) : undefined}
          >
            {editingTranscript ? (
              <div className="editor-stack">
                <textarea
                  className="editor-textarea transcript-editor"
                  value={transcriptDraft}
                  onChange={(event) => setTranscriptDraft(event.target.value)}
                  placeholder="输入完整转写文本"
                />
                <p className="muted">只修改完整文本，已有时间戳分段会保留。保存后旧分析会标记为需要更新。</p>
                <div className="editor-actions">
                  <button
                    className="button button-primary"
                    onClick={() => submitTranscript(false)}
                    disabled={saveTranscript.isPending || !transcriptDraft.trim()}
                  >
                    {saveTranscript.isPending ? '正在保存…' : '保存转写'}
                  </button>
                  <button
                    className="button button-secondary"
                    onClick={() => submitTranscript(true)}
                    disabled={saveTranscript.isPending || !transcriptDraft.trim()}
                  >
                    保存并重新分析
                  </button>
                  <button className="button button-secondary" onClick={cancelTranscriptEdit} disabled={saveTranscript.isPending}>取消</button>
                </div>
                <InlineError error={saveTranscript.error} />
              </div>
            ) : item.transcript ? (
              <article className="transcript-text">{item.transcript}</article>
            ) : <EmptyState title="暂无转写文本" />}
          </Panel>
          {item.segments.length ? (
            <Panel title="时间戳分段" description={`${item.segments.length} 个片段 · 点击任意片段开始播放`}>
              <div className="segments evidence-segments">
                {item.segments.map((segment, index) => (
                  <button
                    type="button"
                    className={`segment segment-button${activeSegmentIndex === index ? ' is-active' : ''}`}
                    key={`${segment.start}-${index}`}
                    ref={(element) => { segmentRefs.current[index] = element }}
                    onClick={() => playFrom(segment.start, index)}
                    aria-current={activeSegmentIndex === index ? 'true' : undefined}
                  >
                    <span>▶ {formatDuration(segment.start)} – {formatDuration(segment.end)}</span>
                    <p>{segment.text}</p>
                  </button>
                ))}
              </div>
            </Panel>
          ) : null}
        </div>
        <aside className="detail-aside page-stack">
          <Panel title="音频" description={activeSegmentIndex !== null ? `正在定位片段 ${activeSegmentIndex + 1}` : '点击观点来源或转写片段可直接定位'}>
            {item.audioUrl ? (
              <>
                <audio
                  ref={audioRef}
                  className="audio-player"
                  controls
                  preload="metadata"
                  src={item.audioUrl}
                  onLoadedMetadata={applyDeepLink}
                  onTimeUpdate={handleTimeUpdate}
                />
                <div className="playback-toolbar">
                  <span>当前位置 <strong>{formatDuration(currentTime)}</strong></span>
                  <button type="button" className="button button-secondary" onClick={() => { void copyCurrentLink() }}>复制时间链接</button>
                </div>
                {playbackNotice ? <p className="playback-notice">{playbackNotice}</p> : null}
                {copyNotice ? <p className="copy-notice">{copyNotice}</p> : null}
              </>
            ) : <p className="muted">暂无可播放音频</p>}
            <dl className="meta-list">
              <div><dt>文件大小</dt><dd>{formatBytes(item.audioSize)}</dd></div>
              <div><dt>转写模型</dt><dd>{item.transcriptionModel || '—'}</dd></div>
              <div><dt>分析模型</dt><dd>{item.analysisModel || '—'}</dd></div>
            </dl>
          </Panel>
          <Panel title="处理操作" description="继续当前流程，或从指定阶段重新生成结果。">
            <div className="form-stack">
              <label className="field">
                <span>起始阶段</span>
                <select value={stage} onChange={(event) => setStage(event.target.value as VideoProcessStage)}>
                  <option value="current">根据当前状态继续</option>
                  <option value="audio">重新提取音频</option>
                  <option value="transcription">重新转写</option>
                  <option value="analysis">重新分析</option>
                </select>
              </label>
              <label className="check-field">
                <input type="checkbox" checked={continueToDone} onChange={(event) => setContinueToDone(event.target.checked)} />
                继续执行到 done
              </label>
              <button className="button button-primary full-width" onClick={() => process.mutate()} disabled={process.isPending}>
                {process.isPending ? '正在提交…' : '启动处理任务'}
              </button>
              <InlineError error={process.error} />
            </div>
          </Panel>
          <Panel title="创作者">
            <Link className="creator-link" to={`/creators/${encodeURIComponent(item.creatorSecUid)}`}>
              <strong>{item.creatorName || '未命名创作者'}</strong>
              <small>{item.creatorSecUid}</small>
            </Link>
          </Panel>
        </aside>
      </div>
    </>
  )
}
