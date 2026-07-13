import { type FormEvent, useMemo, useState } from 'react'
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
import type { ProcessingJob, VideoProcessStage } from './types'

const videoStatuses = [
  '',
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

function useOpenJob() {
  const navigate = useNavigate()
  return (job: ProcessingJob) => navigate(`/jobs?focus=${job.id}`)
}

export function DashboardPage() {
  const openJob = useOpenJob()
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard })
  const scan = useMutation({ mutationFn: () => api.scan(true), onSuccess: openJob })
  const pipeline = useMutation({
    mutationFn: () => api.pipeline({ scan: true, maxTasks: 40 }),
    onSuccess: openJob,
  })

  return (
    <>
      <PageHeader
        eyebrow="知识工作台"
        title="穿透声音，洞察思想"
        description="查看内容处理进度，阅读转写与分析结果，并从页面直接启动全链路处理。"
        actions={
          <>
            <button className="button button-secondary" onClick={() => scan.mutate()} disabled={scan.isPending}>
              {scan.isPending ? '正在提交…' : '扫描新增内容'}
            </button>
            <button className="button button-primary" onClick={() => pipeline.mutate()} disabled={pipeline.isPending}>
              {pipeline.isPending ? '正在提交…' : '运行完整流程'}
            </button>
          </>
        }
      />
      <InlineError error={scan.error || pipeline.error} />
      {dashboard.isLoading ? <LoadingState /> : null}
      {dashboard.isError ? <ErrorState error={dashboard.error} retry={() => dashboard.refetch()} /> : null}
      {dashboard.data ? (
        <div className="page-stack">
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
        </div>
      ) : null}
    </>
  )
}

export function VideosPage() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [status, setStatus] = useState(params.get('status') ?? '')
  const [tag, setTag] = useState(params.get('tag') ?? '')
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

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    if (q.trim()) next.set('q', q.trim())
    if (status) next.set('status', status)
    if (tag) next.set('tag', tag)
    const creator = params.get('creator')
    if (creator) next.set('creator', creator)
    setParams(next)
  }

  return (
    <>
      <PageHeader eyebrow="内容库" title="视频" description="浏览所有处理状态，按关键词、标签或状态筛选内容。" />
      <Panel className="filter-panel">
        <form className="filter-bar" onSubmit={submit}>
          <label className="field grow">
            <span>关键词</span>
            <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="描述、摘要、观点或转写" />
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
      queryClient.invalidateQueries({ queryKey: ['video', videoId] })
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
        </form>
      </Panel>
      {creators.isLoading ? <LoadingState /> : null}
      {creators.isError ? <ErrorState error={creators.error} retry={() => creators.refetch()} /> : null}
      {creators.data ? (
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
        actions={<Link className="button button-secondary" to={`/videos?creator=${encodeURIComponent(data.creator.secUid)}`}>查看全部视频</Link>}
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
  const [q, setQ] = useState(currentQuery)
  const [tag, setTag] = useState(params.get('tag') ?? '')
  const results = useQuery({
    queryKey: ['search', currentQuery, params.get('tag') ?? ''],
    queryFn: () => api.search(currentQuery, undefined, params.get('tag') ?? undefined, 100),
    enabled: Boolean(currentQuery),
  })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => api.tags(undefined, 100) })
  return (
    <>
      <PageHeader eyebrow="全文检索" title="搜索知识内容" description="同时搜索描述、摘要、转写、标签和关键观点。" />
      <Panel className="search-hero">
        <form className="search-form" onSubmit={(event) => {
          event.preventDefault()
          const next = new URLSearchParams()
          if (q.trim()) next.set('q', q.trim())
          if (tag) next.set('tag', tag)
          setParams(next)
        }}>
          <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="输入想查找的主题、人物或观点" autoFocus />
          <select value={tag} onChange={(event) => setTag(event.target.value)}>
            <option value="">全部标签</option>
            {tags.data?.items.map((item) => <option key={item.tag} value={item.tag}>{item.tag}</option>)}
          </select>
          <button className="button button-primary">搜索</button>
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
  const focusId = Number(params.get('focus'))
  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.jobs({ limit: 100 }),
    refetchInterval: (query) => query.state.data?.items.some((job) => job.status === 'queued' || job.status === 'running') ? 2000 : 10000,
  })
  const focused = useMemo(() => jobs.data?.items.find((job) => job.id === focusId), [jobs.data, focusId])

  return (
    <>
      <PageHeader eyebrow="运行中心" title="处理任务" description="查看扫描、完整 pipeline 和单视频重跑的实时状态与结果。" actions={<button className="button button-secondary" onClick={() => jobs.refetch()}>刷新</button>} />
      {jobs.isLoading ? <LoadingState /> : null}
      {jobs.isError ? <ErrorState error={jobs.error} retry={() => jobs.refetch()} /> : null}
      {focused ? <JobDetail job={focused} close={() => { const next = new URLSearchParams(params); next.delete('focus'); setParams(next) }} /> : null}
      {jobs.data ? (
        <Panel title={`最近任务 · ${jobs.data.total}`}>
          {jobs.data.items.length ? (
            <div className="job-list">
              {jobs.data.items.map((job) => (
                <button className={`job-row${job.id === focusId ? ' is-selected' : ''}`} key={job.id} onClick={() => { const next = new URLSearchParams(params); next.set('focus', String(job.id)); setParams(next) }}>
                  <span className="job-id">#{job.id}</span>
                  <span><strong>{job.jobType}</strong><small>{formatDate(job.createdAt)}</small></span>
                  {job.videoId ? <span>视频 #{job.videoId}</span> : <span>全局任务</span>}
                  <JobBadge status={job.status} />
                </button>
              ))}
            </div>
          ) : <EmptyState title="暂无任务" />}
        </Panel>
      ) : null}
    </>
  )
}

function JobDetail({ job, close }: { job: ProcessingJob; close: () => void }) {
  return (
    <Panel className="job-detail" title={`任务 #${job.id}`} action={<button className="icon-button" onClick={close} aria-label="关闭">×</button>}>
      <div className="job-detail-grid">
        <div><span>类型</span><strong>{job.jobType}</strong></div>
        <div><span>状态</span><JobBadge status={job.status} /></div>
        <div><span>开始</span><strong>{formatDate(job.startedAt)}</strong></div>
        <div><span>完成</span><strong>{formatDate(job.finishedAt)}</strong></div>
      </div>
      {job.errorMessage ? <p className="inline-error">{job.errorMessage}</p> : null}
      <details open={job.status === 'failed' || job.status === 'succeeded'}>
        <summary>请求与执行结果</summary>
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
