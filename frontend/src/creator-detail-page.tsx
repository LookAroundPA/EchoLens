import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, formatDuration } from './api'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatCard,
  StatusBadge,
  TagPills,
  VideoCard,
} from './components'
import type { CreatorPointSource, RepresentativeVideo } from './types'
import './creator-detail-page.css'

function sourcePath(source: CreatorPointSource): string {
  const params = new URLSearchParams()
  if (source.start !== null) params.set('t', String(Math.max(0, source.start)))
  if (source.segmentIndex !== null) params.set('segment', String(source.segmentIndex))
  const suffix = params.toString()
  return `/videos/${source.videoId}${suffix ? `?${suffix}` : ''}`
}

function SourceLink({ source }: { source: CreatorPointSource }) {
  const time = source.start !== null
    ? `${formatDuration(source.start)}${source.end !== null ? ` – ${formatDuration(source.end)}` : ''}`
    : null
  return (
    <Link className="creator-source" to={sourcePath(source)}>
      <div>
        <strong>{source.title}</strong>
        <small>{formatDate(source.publishedAt)}</small>
      </div>
      {source.excerpt ? <p>{source.excerpt}</p> : null}
      <span>{time ? `▶ ${time} 打开来源` : '打开来源 →'}</span>
    </Link>
  )
}

function RepresentativeCard({ video }: { video: RepresentativeVideo }) {
  return (
    <Link className="representative-card" to={`/videos/${video.id}`}>
      <div className="representative-card-top">
        <StatusBadge status={video.status} />
        <time>{formatDate(video.publishedAt ?? video.updatedAt)}</time>
      </div>
      <h3>{video.description || video.summary || `视频 ${video.videoId}`}</h3>
      <p className="representative-reason">{video.reason}</p>
      <TagPills tags={video.tags} max={5} />
      <span className="representative-open">查看内容与来源 →</span>
    </Link>
  )
}

export function CreatorDetailPage() {
  const { secUid } = useParams()
  const creator = useQuery({
    queryKey: ['creator', secUid],
    queryFn: () => api.creator(secUid || '', 100),
    enabled: Boolean(secUid),
  })

  if (creator.isLoading) return <LoadingState label="正在汇总创作者内容…" />
  if (creator.isError) return <ErrorState error={creator.error} retry={() => { void creator.refetch() }} />
  if (!creator.data) return null

  const data = creator.data
  const profile = data.profile
  const completionRate = data.creator.videoCount
    ? `${Math.round(data.creator.completedCount / data.creator.videoCount * 100)}%`
    : '0%'

  return (
    <>
      <PageHeader
        eyebrow="创作者知识档案"
        title={data.creator.name || '未命名创作者'}
        description={data.creator.secUid}
        actions={(
          <>
            <Link className="button button-primary" to={`/ask?creator=${encodeURIComponent(data.creator.secUid)}`}>问该创作者</Link>
            <Link className="button button-secondary" to={`/search?creator=${encodeURIComponent(data.creator.secUid)}`}>搜索该创作者</Link>
            <Link className="button button-secondary" to={`/videos?creator=${encodeURIComponent(data.creator.secUid)}`}>查看全部视频</Link>
          </>
        )}
      />

      <section className="stats-grid creator-profile-stats">
        <StatCard label="视频总数" value={data.creator.videoCount} hint="严格按 sec_uid 聚合" />
        <StatCard label="已完成" value={data.creator.completedCount} hint={`完成率 ${completionRate}`} />
        <StatCard label="主要主题" value={profile.mainThemes.length} hint="按标签频率汇总" />
        <StatCard label="聚合观点" value={profile.insights.length} hint={`${profile.analyzedVideoCount} 条内容参与汇总`} />
      </section>

      <div className="page-stack creator-profile-stack">
        <Panel title="内容概览" description="根据现有摘要、标签和关键观点实时生成，不额外调用模型。">
          <p className="creator-overview">{profile.overview}</p>
        </Panel>

        <Panel title="主要主题" description="点击主题可在该创作者范围内继续搜索。">
          {profile.mainThemes.length ? (
            <div className="creator-theme-grid">
              {profile.mainThemes.map((theme, index) => (
                <Link
                  key={theme.tag}
                  className="creator-theme"
                  to={`/search?creator=${encodeURIComponent(data.creator.secUid)}&tag=${encodeURIComponent(theme.tag)}&q=${encodeURIComponent(theme.tag)}`}
                >
                  <span>{index + 1}</span>
                  <strong>{theme.tag}</strong>
                  <small>{theme.count} 条内容</small>
                </Link>
              ))}
            </div>
          ) : <EmptyState title="暂无主题" description="完成视频分析后会自动汇总。" />}
        </Panel>

        <Panel title="代表观点与来源" description="相近表述会合并；每条观点最多展示四个视频来源。">
          {profile.insights.length ? (
            <div className="creator-insight-list">
              {profile.insights.map((insight, index) => (
                <article className="creator-insight" key={`${index}-${insight.text}`}>
                  <div className="creator-insight-heading">
                    <span>{index + 1}</span>
                    <div>
                      <h3>{insight.text}</h3>
                      <p>出现在 {insight.occurrenceCount} 个视频中</p>
                    </div>
                  </div>
                  {insight.sources.length ? (
                    <div className="creator-source-list">
                      {insight.sources.map((source) => (
                        <SourceLink key={`${source.videoId}-${source.segmentIndex ?? 'video'}`} source={source} />
                      ))}
                    </div>
                  ) : <p className="muted">暂无可打开来源</p>}
                </article>
              ))}
            </div>
          ) : <EmptyState title="暂无聚合观点" description="现有分析结果还没有足够明确的关键观点。" />}
        </Panel>

        <Panel title="代表视频" description="优先选择摘要、主题、观点和时间来源较完整的内容。">
          {profile.representativeVideos.length ? (
            <div className="representative-grid">
              {profile.representativeVideos.map((video) => <RepresentativeCard key={video.id} video={video} />)}
            </div>
          ) : <EmptyState title="暂无代表视频" />}
        </Panel>

        <Panel title="最近完成内容" description="最近发布且已经完成转写和分析的视频。">
          {profile.recentVideos.length ? (
            <div className="video-grid">
              {profile.recentVideos.map((video) => <VideoCard key={video.id} video={video} />)}
            </div>
          ) : <EmptyState title="暂无已完成内容" />}
        </Panel>

        <Panel title={`全部视频时间线 · ${data.videos.length}`} description="包括处理中和失败状态，便于继续处理。">
          {data.videos.length ? (
            <div className="video-grid">
              {data.videos.map((video) => <VideoCard key={video.id} video={video} />)}
            </div>
          ) : <EmptyState title="暂无视频" />}
        </Panel>
      </div>
    </>
  )
}
