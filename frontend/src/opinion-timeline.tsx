import { useMemo, useRef, useState, type WheelEvent as ReactWheelEvent } from 'react'
import { Link } from 'react-router-dom'
import { formatDate } from './api'
import { StatusBadge, TagPills } from './components'
import type { VideoSummary } from './types'
import './opinion-timeline.css'

const DAY_MS = 86_400_000
const MIN_ZOOM = 0.25
const MAX_ZOOM = 24
const TRACK_PADDING = 48
const TARGET_TRACK_WIDTH = 1200
const TICK_STEP_DAYS = [1, 2, 3, 5, 7, 14, 30, 60, 90, 182, 365, 730]

interface TimelinePoint {
  video: VideoSummary
  date: Date
}

interface HoverState {
  video: VideoSummary
  x: number
  y: number
}

function baseScaleForSpan(spanDays: number): number {
  const raw = TARGET_TRACK_WIDTH / Math.max(spanDays, 1)
  return Math.min(48, Math.max(2, raw))
}

function tickIntervalDays(pxPerDay: number): number {
  for (const days of TICK_STEP_DAYS) {
    if (days * pxPerDay >= 96) return days
  }
  return TICK_STEP_DAYS[TICK_STEP_DAYS.length - 1]
}

function tickLabel(date: Date, intervalDays: number): string {
  if (intervalDays >= 365) return `${date.getFullYear()}`
  if (intervalDays >= 30) return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function OpinionTimeline({ videos }: { videos: VideoSummary[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [zoom, setZoom] = useState(1)
  const [hover, setHover] = useState<HoverState | null>(null)

  const points = useMemo<TimelinePoint[]>(() => {
    return videos
      .filter((video) => Boolean(video.publishedAt))
      .map((video) => ({ video, date: new Date(video.publishedAt as string) }))
      .sort((a, b) => a.date.getTime() - b.date.getTime())
  }, [videos])

  const undatedCount = videos.length - points.length

  const span = useMemo(() => {
    if (!points.length) return null
    const minDate = points[0].date
    const maxDate = points[points.length - 1].date
    const spanDays = Math.max(1, (maxDate.getTime() - minDate.getTime()) / DAY_MS)
    return { minDate, maxDate, spanDays }
  }, [points])

  if (!points.length || !span) {
    return (
      <div className="state-box">
        <strong>暂无可展示的时间点</strong>
        <p>{undatedCount > 0 ? '现有视频缺少发布时间，暂时无法绘制时间线。' : '还没有已收录的视频。'}</p>
      </div>
    )
  }

  const basePxPerDay = baseScaleForSpan(span.spanDays)
  const pxPerDay = basePxPerDay * zoom
  const trackWidth = span.spanDays * pxPerDay + TRACK_PADDING * 2

  const positionFor = (date: Date) =>
    TRACK_PADDING + ((date.getTime() - span.minDate.getTime()) / DAY_MS) * pxPerDay

  const interval = tickIntervalDays(pxPerDay)
  const ticks: { left: number; label: string }[] = []
  for (
    let cursor = span.minDate.getTime();
    cursor <= span.maxDate.getTime() + interval * DAY_MS;
    cursor += interval * DAY_MS
  ) {
    const date = new Date(cursor)
    ticks.push({ left: positionFor(date), label: tickLabel(date, interval) })
  }

  const applyZoom = (nextZoom: number, anchorClientX?: number) => {
    const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom))
    const container = containerRef.current
    if (!container) {
      setZoom(clamped)
      return
    }
    const rect = container.getBoundingClientRect()
    const anchorOffset = (anchorClientX ?? rect.left + container.clientWidth / 2) - rect.left
    const contentX = container.scrollLeft + anchorOffset
    const ratio = clamped / zoom
    setZoom(clamped)
    requestAnimationFrame(() => {
      if (containerRef.current) {
        containerRef.current.scrollLeft = contentX * ratio - anchorOffset
      }
    })
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    const container = containerRef.current
    if (!container) return
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault()
      applyZoom(zoom * (event.deltaY > 0 ? 0.88 : 1.14), event.clientX)
      return
    }
    const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
    if (delta !== 0) {
      event.preventDefault()
      container.scrollLeft += delta
    }
  }

  return (
    <div className="opinion-timeline">
      <div className="opinion-timeline-toolbar">
        <span className="opinion-timeline-hint">
          共 {points.length} 个时间点 · Ctrl/⌘ + 滚轮缩放 · 滚轮或拖动横向滚动
          {undatedCount > 0 ? ` · ${undatedCount} 条无发布时间未显示` : ''}
        </span>
        <div className="opinion-timeline-zoom">
          <button type="button" onClick={() => applyZoom(zoom / 1.4)} aria-label="缩小">－</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => applyZoom(zoom * 1.4)} aria-label="放大">＋</button>
          <button type="button" onClick={() => applyZoom(1)}>重置</button>
        </div>
      </div>

      <div className="opinion-timeline-scroll" ref={containerRef} onWheel={handleWheel}>
        <div className="opinion-timeline-track" style={{ width: `${trackWidth}px` }}>
          <div className="opinion-timeline-axis" />

          {ticks.map((tick) => (
            <div className="opinion-timeline-tick" key={tick.left} style={{ left: `${tick.left}px` }}>
              <span className="opinion-timeline-tick-mark" />
              <span className="opinion-timeline-tick-label">{tick.label}</span>
            </div>
          ))}

          {points.map(({ video, date }) => (
            <Link
              key={video.id}
              to={`/videos/${video.id}`}
              className={`opinion-timeline-point status--${video.status}`}
              style={{ left: `${positionFor(date)}px` }}
              onMouseEnter={(event) => {
                const rect = event.currentTarget.getBoundingClientRect()
                setHover({ video, x: rect.left + rect.width / 2, y: rect.top })
              }}
              onMouseLeave={() => setHover(null)}
            >
              <span className="opinion-timeline-dot" />
            </Link>
          ))}
        </div>
      </div>

      {hover ? <TimelineTooltip hover={hover} /> : null}
    </div>
  )
}

function TimelineTooltip({ hover }: { hover: HoverState }) {
  const { video } = hover
  const width = 320
  const clampedX = Math.min(Math.max(hover.x, width / 2 + 12), window.innerWidth - width / 2 - 12)
  const flipDown = hover.y < 220

  return (
    <div
      className={`opinion-timeline-tooltip${flipDown ? ' opinion-timeline-tooltip--down' : ''}`}
      style={{ left: `${clampedX}px`, top: `${hover.y}px`, width: `${width}px` }}
    >
      <div className="opinion-timeline-tooltip-head">
        <StatusBadge status={video.status} />
        <time>{formatDate(video.publishedAt)}</time>
      </div>
      <h4>{video.description || video.summary || `视频 ${video.videoId}`}</h4>
      {video.summary ? <p>{video.summary}</p> : <p className="muted">暂无分析摘要</p>}
      <TagPills tags={video.tags} max={5} />
      <span className="opinion-timeline-tooltip-open">查看完整分析 →</span>
    </div>
  )
}
