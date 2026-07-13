import { type FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, formatBytes, formatDate, formatDuration } from './api'
import {
  EmptyState,
  ErrorState,
  InlineError,
  JobBadge,
  LoadingState,
  PageHeader,
  Panel,
  StatCard,
  StatusBadge,
  TagCloud,
  TagPills,
  VideoCard,
} from './components'
import type { JobStatus, ProcessingJob, VideoProcessStage } from './types'

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

const jobStatuses: Array<JobStatus | ''> = ['', 'queued', 'running', 'succeeded', 'failed']
const jobTypes = ['', 'scan', 'pipeline', 'video_process']

const jobTypeLabels: Record<string, string> = {
  scan: '扫描内容源',
  pipeline: '完整处理流程',
  video_process: '单视频处理',
}

const metricLabels: Record<string, string> = {
  discovered: '发现',
  skipped: '跳过',
  inserted: '新增入库',
  queued: '已入队',
  skippedExisting: '已存在',
  processed: '已处理',
  completed: '已完成',
  failed: '失败',
  enqueue: '入队',
  finalStatus: '最终状态',
  requestedStage: '请求阶段',
  resolvedStage: '实际阶段',
  continueToDone: '继续到完成',
}

function useOpenJob() {
  const navigate = useNavigate()
  return (job: ProcessingJob) => navigate(`/jobs?focus=${job.id}`)
}

function optionalTaskLimit(value: string): number | undefined {
  if (!value.trim()) return undefined
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 10_000) {
    throw new Error('每阶段处理数量必须是 1 到 10000 之间的整数')
  }
  return parsed
}

function displayMetric(value: unknown): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function metricEntries(value: unknown): Array<[string, unknown]> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  return Object.entries(value as Record<string, unknown>).filter(([, item]) => typeof item !== 'object' || item === null)
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
    audio: '音频提取',
    transcription: '语音转写',
    analysis: '内容分析',
  }
  return labels[stage] ?? stage
}

export function DashboardPage() {
  const openJob = useOpenJob()
  const [enqueueScan, setEnqueueScan] = useState(true)
  const [scanBeforePipeline, setScanBeforePipeline] = useState(true)
  const [maxTasks, setMaxTasks] = useState('40')
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    refetchInterval: 15_000,
  })
  const scan = useMutation({ mutationFn: () => api.scan(enqueueScan), onSuccess: openJob })
  const pipeline = useMutation({
    mutationFn: () => api.pipeline({
      scan: scanBeforePipeline,
      maxTasks: optionalTaskLimit(maxTasks),
    }),
    onSuccess: openJob,
  })

  return (
    <>
      <PageHeader
        eyebrow="知识工作台"
        title="穿透声音，洞察思想"
        description="查看内容处理进度，阅读转写与分析结果，并从页面直接启动全链路处理。"
        actions={<button className="button button-secondary" onClick={() => dashboard.refetch()}>刷新数据</button>}
      />
      <div className="page-stack">
        <Panel title="运行操作" description="扫描新增内容，或执行音频、转写和分析完整流程。" className="operation-panel">
          <div className="operation-grid">
            <div className="operation-block">
              <div>
                <strong>扫描内容源</strong>
                <p>检查本地视频和 metadata；可选择将新增内容入库并推送 Redis。</p>
              </div>
              <label className="check-field">
                <input type="checkbox" checked={enqueueScan} onChange={(event) => setEnqueueScan(event.target.checked)} />
                新增内容入库并入队
              </label>
              <button className="button button-secondary" onClick={() => scan.mutate()} disabled={scan.isPending}>
                {scan.isPending ? '正在提交…' : '开始扫描'}
              </button>
            </div>
            <div className="operation-block operation-block-primary">
              <div>
                <strong>运行完整流程</strong>
                <p>依次执行扫描、音频提取、Faster-Whisper 转写和 DeepSeek 分析。</p>
              </div>
              <div className="operation-options">
                <label className="field">
                  <span>每阶段最大处理数量</span>
                  <input
                    type="number"
                    min="1"
                    max="10000"
                    value={maxTasks}
                    onChange={(event) => setMaxTasks(event.target.value)}
                    placeholder="留空表示处理全部"
                  />
                </label>
                <label className="check-field">
                  <input type="checkbox" checked={scanBeforePipeline} onChange={(event) => setScanBeforePipeline(event.target.checked)} />
                  运行前先扫描新增内容
                </label>
              </div>
              <button className="button button-primary" onClick={() => pipeline.mutate()} disabled={pipeline.isPending}>
                {pipeline.isPending ? '正在提交…' : '运行完整流程'}
              </button>
            </div>
          </div>
          <InlineError error={scan.error || pipeline.error} />
        </Panel>

        {dashboard.isLoading ? <LoadingState /> : null}
        {dashboard.isError ? <ErrorState error={dashboard.error} retry={() => dashboard.refetch()} /> : null}
        {dashboard.data ? (
          <>
            <section className="stats-grid">
              <StatCard label="创作者" value={dashboard.data.creatorCount} hint="稳定身份已入库" />
              <StatCard label="视频总数" value={dashboard.data.videoCount} hint="所有处理状态" />
              <StatCard label="已完成" value={dashboard.data.completedCount} hint="转写与分析完成" />
              <StatCard
                label="完成率"
                value={dashboard.data.videoCount ? `${Math.round(dashboard.data.completedCount / dashboard.data.videoCount * 100)}%` : '0%'}
                hint="done / total"
              />
            </section>

            <div className="two-column-grid">
              <Panel title="处理状态" description="当前视频在全链路中的分布">
                <div className="status-overview">
                  {Object.entries(dashboard.data.statusCounts).map(([status, count]) => (
                    <Link key={status} to={`/videos?status=${encodeURIComponent(status)}`}>
                      <StatusBadge status={status} />
                      <strong>{count}</strong>
                    </Link>
                  ))}
                </div>
              </Panel>
              <Panel title="高频标签" description="DeepSeek 分析结果中的主题">
                <TagCloud items={dashboard.data.topTags} />
              </Panel>
            </div>

            <Panel title="最近更新" description="最新进入或推进处理状态的视频" action={<Link className="text-link" to="/videos">查看全部</Link>}>
              {dashboard.data.recentVideos.length ? (
                <div className="video-grid">
                  {dashboard.data.recentVideos.map((video) => <VideoCard key={video.id} video={video} />)}
                </div>
              ) : <EmptyState title="暂无视频" description="先扫描本地内容源并运行处理流程。" />}
            </Panel>
          </>
        ) : null}
      </div>
    </>
  )
}

export function VideosPage() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [status, setStatus] = useState(params.get('status') ?? '')
  const [tag, setTag] = useState(params.get('tag') ?? '')
  const [creator, setCreator] = useState(params.get('creator') ?? '')
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
  const videos = useQuery({ queryKey: ['videos', active], queryFn: () => api.videos(active) })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => api.tags(undefined, 100) })
  const creators = useQuery({ queryKey: ['creators', 'video-filter'], queryFn: () => api.creators(undefined, 500) })

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    if (q.trim()) next.set('q', q.trim())
    if (status) next.set('status', status)
    if (tag) next.set('tag', tag)
    if (creator) next.set('creator', creator)
    setParams(next)
  }

  return (
    <>
      <PageHeader eyebrow="内容库" title="视频" description="浏览所有处理状态，按关键词、创作者、标签或状态筛选内容。" />
      <Panel className="filter-panel">
        <form className="filter-bar filter-bar-wrap" onSubmit={submit}>
          <label className="field grow">
            <span>关键词</span>
            <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="描述、摘要、观点或转写" />
          </label>
          <label className="field">
            <span>创作者</span>
            <select value={creator} onChange={(event) => setCreator(event.target.value)}>
              <option value="">全部创作者</option>
              {creators.data?.items.map((item) => <option key={item.secUid} value={item.secUid}>{item.name || item.secUid}</option>)}
            </select>
          </label>
          <label className="field">
            <span>状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {videoStatuses.map((item) => <option key={item || 'all'} value={item}>{item || '全部状态'}</option>)}
            </select>
          </label>
          <label className="field">
            <span>标签</span>
            <select value={tag} onChange={(event) => setTag(event.target.value)}>
              <option value="">全部标签</option>
              {tags.data?.items.map((item) => <option key={item.tag} value={item.tag}>{item.tag} ({item.count})</option>)}
            </select>
          </label>
          <button className="button button-primary" type="submit">筛选</button>
          <button className="button button-secondary" type="button" onClick={() => {
            setQ('')
            setStatus('')
            setTag('')
            setCreator('')
            setParams({})
          }}>清空</button>
        </form>
      </Panel>
      {videos.isLoading ? <LoadingState /> : null}
      {videos.isError ? <ErrorState error={videos.error} retry={() => videos.refetch()} /> : null}
      {videos.data ? (
        <div className="page-stack">
          <div className="result-line"><strong>{videos.data.total}</strong> 条结果</div>
          {videos.data.items.length ? (
            <div className="video-grid">{videos.data.items.map((video) => <VideoCard key={video.id} video={video} />)}</div>
          ) : <EmptyState title="没有匹配内容" description="调整筛选条件或先运行处理流程。" />}
          <div className="pagination">
            <button className="button button-secondary" disabled={offset <= 0} onClick={() => {
              const next = new URLSearchParams(params)
              next.set('offset', String(Math.max(0, offset - limit)))
              setParams(next)
            }}>上一页</button>
            <span>第 {Math.floor(offset / limit) + 1} 页</span>
            <button className="button button-secondary" disabled={offset + limit >= videos.data.total} onClick={() => {
              const next = new URLSearchParams(params)
              next.set('offset', String(offset + limit))
              setParams(next)
            }}>下一页</button>
          </div>
        </div>
      ) : null}
    </>
  )
}

export function VideoDetailPage() {
  const { id } = useParams()
  const videoId = Number(id)
  const openJob = useOpenJob()
  const queryClient = useQueryClient()
  const [stage, setStage] = useState<VideoProcessStage>('current')
  const [continueToDone, setContinueToDone] = useState(true)
  const video = useQuery({
    queryKey: ['video', videoId],
    queryFn: () => api.video(videoId),
    enabled: Number.isFinite(videoId),
  })
  const process = useMutation({
    mutationFn: () => api.processVideo(videoId, { stage, continueToDone }),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ['video', videoId] })
      openJob(job)
    },
  })

  if (!Number.isFinite(videoId)) return <ErrorState error={new Error('无效的视频 ID')} />
  if (video.isLoading) return <LoadingState label="正在读取视频详情…" />
  if (video.isError) return <ErrorState error={video.error} retry={() => video.refetch()} />
  if (!video.data) return null

  const item = video.data
  return (
    <>
      <PageHeader
        eyebrow={item.creatorName || '视频详情'}
        title={item.description || `视频 ${item.videoId}`}
        description={`平台 ID：${item.videoId} · ${formatDate(item.publishedAt)}`}
        actions={<StatusBadge status={item.status} />}
      />
      <div className="detail-layout">
        <div className="detail-main page-stack">
          <Panel title="内容摘要">
            <p className="summary-text">{item.summary || '尚未生成摘要。'}</p>
            <TagPills tags={item.tags} />
          </Panel>
          <Panel title="关键观点">
            {item.keyPoints.length ? (
              <ol className="key-points">{item.keyPoints.map((point, index) => <li key={`${index}-${point}`}>{point}</li>)}</ol>
            ) : <EmptyState title="暂无关键观点" />}
          </Panel>
          <Panel title="完整转写" description={item.language ? `识别语言：${item.language}` : undefined}>
            {item.transcript ? <article className="transcript-text">{item.transcript}</article> : <EmptyState title="暂无转写文本" />}
          </Panel>
          {item.segments.length ? (
            <Panel title="时间戳分段" description={`${item.segments.length} 个片段`}>
              <div className="segments">
                {item.segments.map((segment, index) => (
                  <div className="segment" key={`${segment.start}-${index}`}>
                    <span>{formatDuration(segment.start)} – {formatDuration(segment.end)}</span>
                    <p>{segment.text}</p>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}
        </div>
        <aside className="detail-aside page-stack">
          <Panel title="音频">
            {item.audioUrl ? <audio className="audio-player" controls preload="metadata" src={item.audioUrl} /> : <p className="muted">暂无可播放音频</p>}
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

export function CreatorsPage() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const creators = useQuery({
    queryKey: ['creators', params.get('q') ?? ''],
    queryFn: () => api.creators(params.get('q') ?? undefined, 500),
  })
  return (
    <>
      <PageHeader eyebrow="内容来源" title="创作者" description="按稳定 sec_uid 聚合创作者及其已处理内容。" />
      <Panel className="filter-panel">
        <form className="filter-bar" onSubmit={(event) => {
          event.preventDefault()
          setParams(q.trim() ? { q: q.trim() } : {})
        }}>
          <label className="field grow"><span>搜索</span><input value={q} onChange={(event) => setQ(event.target.value)} placeholder="创作者名称或 sec_uid" /></label>
          <button className="button button-primary">搜索</button>
          <button className="button button-secondary" type="button" onClick={() => { setQ(''); setParams({}) }}>清空</button>
        </form>
      </Panel>
      {creators.isLoading ? <LoadingState /> : null}
      {creators.isError ? <ErrorState error={creators.error} retry={() => creators.refetch()} /> : null}
      {creators.data ? (
        creators.data.items.length ? (
          <div className="creator-grid">
            {creators.data.items.map((creator) => (
              <Link className="creator-card" key={creator.secUid} to={`/creators/${encodeURIComponent(creator.secUid)}`}>
                <div className="avatar">{(creator.name || 'E').slice(0, 1)}</div>
                <div className="creator-card-body">
                  <h2>{creator.name || '未命名创作者'}</h2>
                  <p>{creator.secUid}</p>
                  <div className="creator-counts"><span>{creator.videoCount} 视频</span><span>{creator.completedCount} 已完成</span></div>
                  <TagPills tags={creator.topTags} max={5} />
                </div>
              </Link>
            ))}
          </div>
        ) : <EmptyState title="没有匹配的创作者" />
      ) : null}
    </>
  )
}

export function CreatorDetailPage() {
  const { secUid } = useParams()
  const creator = useQuery({
    queryKey: ['creator', secUid],
    queryFn: () => api.creator(secUid || '', 500),
    enabled: Boolean(secUid),
  })
  if (creator.isLoading) return <LoadingState />
  if (creator.isError) return <ErrorState error={creator.error} retry={() => creator.refetch()} />
  if (!creator.data) return null
  const data = creator.data
  return (
    <>
      <PageHeader
        eyebrow="创作者档案"
        title={data.creator.name || '未命名创作者'}
        description={data.creator.secUid}
        actions={
          <>
            <Link className="button button-secondary" to={`/search?creator=${encodeURIComponent(data.creator.secUid)}`}>搜索该创作者</Link>
            <Link className="button button-secondary" to={`/videos?creator=${encodeURIComponent(data.creator.secUid)}`}>查看全部视频</Link>
          </>
        }
      />
      <section className="stats-grid stats-grid-compact">
        <StatCard label="视频" value={data.creator.videoCount} />
        <StatCard label="已完成" value={data.creator.completedCount} />
        <StatCard label="完成率" value={data.creator.videoCount ? `${Math.round(data.creator.completedCount / data.creator.videoCount * 100)}%` : '0%'} />
      </section>
      <div className="page-stack">
        <Panel title="主题标签"><TagCloud items={data.topTags} /></Panel>
        <Panel title="视频时间线">
          {data.videos.length ? <div className="video-grid">{data.videos.map((video) => <VideoCard key={video.id} video={video} />)}</div> : <EmptyState title="暂无视频" />}
        </Panel>
      </div>
    </>
  )
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const currentQuery = params.get('q') ?? ''
  const currentCreator = params.get('creator') ?? ''
  const currentTag = params.get('tag') ?? ''
  const [q, setQ] = useState(currentQuery)
  const [tag, setTag] = useState(currentTag)
  const [creator, setCreator] = useState(currentCreator)
  const results = useQuery({
    queryKey: ['search', currentQuery, currentCreator, currentTag],
    queryFn: () => api.search(currentQuery, currentCreator || undefined, currentTag || undefined, 100),
    enabled: Boolean(currentQuery),
  })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => api.tags(undefined, 100) })
  const creators = useQuery({ queryKey: ['creators', 'search-filter'], queryFn: () => api.creators(undefined, 500) })
  return (
    <>
      <PageHeader eyebrow="全文检索" title="搜索知识内容" description="同时搜索描述、摘要、转写、标签和关键观点。" />
      <Panel className="search-hero">
        <form className="search-form search-form-expanded" onSubmit={(event) => {
          event.preventDefault()
          const next = new URLSearchParams()
          if (q.trim()) next.set('q', q.trim())
          if (creator) next.set('creator', creator)
          if (tag) next.set('tag', tag)
          setParams(next)
        }}>
          <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="输入想查找的主题、人物或观点" autoFocus />
          <select value={creator} onChange={(event) => setCreator(event.target.value)}>
            <option value="">全部创作者</option>
            {creators.data?.items.map((item) => <option key={item.secUid} value={item.secUid}>{item.name || item.secUid}</option>)}
          </select>
          <select value={tag} onChange={(event) => setTag(event.target.value)}>
            <option value="">全部标签</option>
            {tags.data?.items.map((item) => <option key={item.tag} value={item.tag}>{item.tag}</option>)}
          </select>
          <button className="button button-primary">搜索</button>
          <button className="button button-secondary" type="button" onClick={() => {
            setQ('')
            setCreator('')
            setTag('')
            setParams({})
          }}>清空</button>
        </form>
      </Panel>
      {!currentQuery ? <EmptyState title="输入关键词开始搜索" description="例如：人工智能、商业模式、教育。" /> : null}
      {results.isLoading ? <LoadingState /> : null}
      {results.isError ? <ErrorState error={results.error} retry={() => results.refetch()} /> : null}
      {results.data ? (
        <div className="page-stack">
          <div className="result-line">“{currentQuery}” 找到 <strong>{results.data.total}</strong> 条结果</div>
          {results.data.items.length ? <div className="video-grid">{results.data.items.map((video) => <VideoCard key={video.id} video={video} />)}</div> : <EmptyState title="没有匹配内容" />}
        </div>
      ) : null}
    </>
  )
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
    refetchInterval: (query) => query.state.data?.items.some((job) => job.status === 'queued' || job.status === 'running') ? 2000 : 10_000,
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

  return (
    <>
      <PageHeader
        eyebrow="运行中心"
        title="处理任务"
        description="查看扫描、完整 pipeline 和单视频重跑的实时状态与结构化结果。"
        actions={<button className="button button-secondary" onClick={() => { jobs.refetch(); focusedJob.refetch() }}>刷新</button>}
      />
      <Panel className="filter-panel">
        <form className="filter-bar" onSubmit={applyFilters}>
          <label className="field">
            <span>任务状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {jobStatuses.map((item) => <option key={item || 'all'} value={item}>{item || '全部状态'}</option>)}
            </select>
          </label>
          <label className="field">
            <span>任务类型</span>
            <select value={jobType} onChange={(event) => setJobType(event.target.value)}>
              {jobTypes.map((item) => <option key={item || 'all'} value={item}>{item ? jobTypeLabels[item] : '全部类型'}</option>)}
            </select>
          </label>
          <button className="button button-primary">筛选</button>
          <button className="button button-secondary" type="button" onClick={() => {
            setStatus('')
            setJobType('')
            setParams({})
          }}>清空</button>
        </form>
      </Panel>
      {focusedJob.isLoading ? <LoadingState label="正在读取任务详情…" /> : null}
      {focusedJob.isError ? <ErrorState error={focusedJob.error} retry={() => focusedJob.refetch()} /> : null}
      {focusedJob.data ? <JobDetail job={focusedJob.data} close={() => { const next = new URLSearchParams(params); next.delete('focus'); setParams(next) }} /> : null}
      {jobs.isLoading ? <LoadingState /> : null}
      {jobs.isError ? <ErrorState error={jobs.error} retry={() => jobs.refetch()} /> : null}
      {jobs.data ? (
        <Panel title={`任务列表 · ${jobs.data.total}`}>
          {jobs.data.items.length ? (
            <div className="job-list">
              {jobs.data.items.map((job) => (
                <button className={`job-row${job.id === focusId ? ' is-selected' : ''}`} key={job.id} onClick={() => { const next = new URLSearchParams(params); next.set('focus', String(job.id)); setParams(next) }}>
                  <span className="job-id">#{job.id}</span>
                  <span><strong>{jobTypeLabels[job.jobType] ?? job.jobType}</strong><small>{formatDate(job.createdAt)}</small></span>
                  {job.videoId ? <span>视频 #{job.videoId}</span> : <span>全局任务</span>}
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

function JobDetail({ job, close }: { job: ProcessingJob; close: () => void }) {
  const stages = jobStageEntries(job)
  const resultMetrics = job.result ? metricEntries(job.result).filter(([key]) => key !== 'stages') : []
  return (
    <Panel className="job-detail" title={`任务 #${job.id} · ${jobTypeLabels[job.jobType] ?? job.jobType}`} action={<button className="icon-button" onClick={close} aria-label="关闭">×</button>}>
      <div className="job-detail-grid">
        <div><span>状态</span><JobBadge status={job.status} /></div>
        <div><span>创建时间</span><strong>{formatDate(job.createdAt)}</strong></div>
        <div><span>开始时间</span><strong>{formatDate(job.startedAt)}</strong></div>
        <div><span>完成时间</span><strong>{formatDate(job.finishedAt)}</strong></div>
      </div>
      {job.videoId ? <Link className="job-video-link" to={`/videos/${job.videoId}`}>打开关联视频 #{job.videoId} →</Link> : null}
      {job.errorMessage ? <p className="inline-error">{job.errorMessage}</p> : null}
      {(job.status === 'queued' || job.status === 'running') ? (
        <div className="job-running-note"><span className="spinner" />任务正在后台执行，页面会自动刷新状态。</div>
      ) : null}
      {stages.length ? (
        <div className="job-stages">
          {stages.map(([stage, value]) => (
            <article className="job-stage" key={stage}>
              <div className="job-stage-header"><span>{stageLabel(stage)}</span><strong>已执行</strong></div>
              <div className="stage-metrics">
                {metricEntries(value).map(([key, metric]) => (
                  <div key={key}><span>{metricLabels[key] ?? key}</span><strong>{displayMetric(metric)}</strong></div>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : null}
      {resultMetrics.length ? (
        <div className="result-metrics">
          {resultMetrics.map(([key, value]) => <div key={key}><span>{metricLabels[key] ?? key}</span><strong>{displayMetric(value)}</strong></div>)}
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

export function NotFoundPage() {
  return (
    <div className="not-found">
      <span>404</span>
      <h1>页面不存在</h1>
      <Link className="button button-primary" to="/">返回总览</Link>
    </div>
  )
}
