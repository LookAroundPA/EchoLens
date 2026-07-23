import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { api, formatDate } from './api'
import type { JobStatus, TagCount, VideoStatus, VideoSummary } from './types'

const navItems = [
  { to: '/', label: '市场雷达', mark: '◉' },
  { to: '/operations', label: '运行中心', mark: '◫' },
  { to: '/videos', label: '视频', mark: '▶' },
  { to: '/creators', label: '创作者', mark: '◎' },
  { to: '/search', label: '搜索', mark: '⌕' },
  { to: '/ask', label: '问答', mark: '✦' },
  { to: '/jobs', label: '任务', mark: '↻' },
]

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    retry: false,
    refetchInterval: 10_000,
  })
  const healthState = health.isLoading ? 'checking' : health.isSuccess ? 'online' : 'offline'
  const healthLabel = healthState === 'checking' ? '正在检查 API' : healthState === 'online' ? 'API 已连接' : 'API 未连接'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/">
          <span className="brand-mark">E</span>
          <span>
            <strong>EchoLens</strong>
            <small>See beyond the sound</small>
          </span>
        </Link>
        <nav className="nav-list" aria-label="主导航">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => {
                const radarTopicActive = item.to === '/' && location.pathname.startsWith('/topics/')
                return `nav-item${isActive || radarTopicActive ? ' is-active' : ''}`
              }}
            >
              <span className="nav-mark" aria-hidden="true">{item.mark}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button
          type="button"
          className={`sidebar-note api-state api-state--${healthState}`}
          onClick={() => health.refetch()}
          title={health.isError ? '点击重新检查 API' : '点击刷新连接状态'}
        >
          <span className="live-dot" />
          <span>{healthLabel}</span>
        </button>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  )
}

export function Panel({
  title,
  description,
  action,
  children,
  className = '',
}: {
  title?: string
  description?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`.trim()}>
      {title || action ? (
        <div className="panel-header">
          <div>
            {title ? <h2>{title}</h2> : null}
            {description ? <p>{description}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  )
}

export function StatCard({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </article>
  )
}

export function StatusBadge({ status }: { status: VideoStatus }) {
  const labels: Record<string, string> = {
    pending: '待处理',
    queued: '已入队',
    processing: '提取音频',
    audio_done: '音频完成',
    transcribing: '转写中',
    transcribed: '转写完成',
    analyzing: '分析中',
    done: '已完成',
    transcription_failed: '转写失败',
    analysis_failed: '分析失败',
  }
  return <span className={`status status--${status}`}>{labels[status] ?? status}</span>
}

export function JobBadge({ status }: { status: JobStatus }) {
  const labels: Record<JobStatus, string> = {
    queued: '排队中',
    running: '执行中',
    succeeded: '成功',
    failed: '失败',
  }
  return <span className={`job-status job-status--${status}`}>{labels[status]}</span>
}

export function TagPills({ tags, max }: { tags: string[]; max?: number }) {
  const shown = max ? tags.slice(0, max) : tags
  if (!shown.length) return <span className="muted">暂无标签</span>
  return (
    <div className="tag-list">
      {shown.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
    </div>
  )
}

export function TagCloud({ items }: { items: TagCount[] }) {
  if (!items.length) return <EmptyState title="暂无标签" description="完成 DeepSeek 分析后会在这里出现。" />
  const max = Math.max(...items.map((item) => item.count), 1)
  return (
    <div className="tag-cloud">
      {items.map((item) => (
        <Link
          key={item.tag}
          to={`/videos?tag=${encodeURIComponent(item.tag)}`}
          style={{ '--weight': 0.85 + item.count / max * 0.35 } as React.CSSProperties}
        >
          {item.tag}<small>{item.count}</small>
        </Link>
      ))}
    </div>
  )
}

export function VideoCard({ video }: { video: VideoSummary }) {
  return (
    <Link className="video-card" to={`/videos/${video.id}`}>
      <div className="video-card-top">
        <StatusBadge status={video.status} />
        <time>{formatDate(video.publishedAt ?? video.updatedAt)}</time>
      </div>
      <h3>{video.description || video.summary || `视频 ${video.videoId}`}</h3>
      {video.summary && video.description ? <p>{video.summary}</p> : null}
      <TagPills tags={video.tags} max={5} />
      <div className="video-card-footer">
        <span>{video.creatorName || '未命名创作者'}</span>
        <span>查看详情 →</span>
      </div>
    </Link>
  )
}

export function LoadingState({ label = '正在读取数据…' }: { label?: string }) {
  return (
    <div className="state-box">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : '发生未知错误'
  return (
    <div className="state-box state-error">
      <strong>加载失败</strong>
      <p>{message}</p>
      {retry ? <button className="button button-secondary" onClick={retry}>重新加载</button> : null}
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="state-box">
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
    </div>
  )
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null
  return <p className="inline-error">{error instanceof Error ? error.message : '操作失败'}</p>
}
