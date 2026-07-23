import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, formatDate } from './api'
import { EmptyState, ErrorState, LoadingState, Panel, StatCard } from './components'
import type {
  CreatorIntelligenceChange,
  CreatorTopicHistorySummary,
  CreatorTopicOpinion,
} from './types'
import './creator-intelligence-panel.css'

const topicTypeLabels: Record<string, string> = {
  stock: '股票',
  industry: '行业',
  index: '指数',
  commodity: '商品',
  currency: '汇率',
  macro: '宏观',
  market: '市场',
}

const stanceLabels: Record<string, string> = {
  strong_bullish: '强烈看多',
  bullish: '看多',
  neutral: '中性',
  cautious: '谨慎',
  bearish: '看空',
  strong_bearish: '强烈看空',
  unclear: '不明确',
}

const sourceLabels: Record<string, string> = {
  explicit: '博主明确观点',
  inferred: 'AI 推导',
}

const horizonLabels: Record<string, string> = {
  intraday: '日内',
  short_term: '短期',
  medium_term: '中期',
  long_term: '长期',
  unspecified: '周期未说明',
}

const confidenceLabels: Record<string, string> = {
  high: '高置信度',
  medium: '中置信度',
  low: '低置信度',
}

const changeLabels: Record<string, string> = {
  first_attention: '首次关注',
  first_mention: '首次关注',
  resumed_attention: '重新关注',
  reversal: '立场反转',
  strengthened: '立场加强',
  weakened: '立场减弱',
  became_cautious: '转为谨慎',
  became_neutral: '转为中性',
  became_unclear: '转为不明确',
  stance_changed: '立场变化',
}

function stanceTone(stance: string): string {
  if (stance === 'strong_bullish' || stance === 'bullish') return 'bullish'
  if (stance === 'strong_bearish' || stance === 'bearish') return 'bearish'
  if (stance === 'cautious') return 'cautious'
  if (stance === 'neutral') return 'neutral'
  return 'unclear'
}

function StanceBadge({ stance }: { stance: string }) {
  return (
    <span className={`creator-intelligence-badge creator-intelligence-badge--${stanceTone(stance)}`}>
      {stanceLabels[stance] ?? stance}
    </span>
  )
}

function TopicHistoryCard({ item }: { item: CreatorTopicHistorySummary }) {
  return (
    <article className="creator-topic-history-card">
      <div className="creator-topic-history-card__header">
        <div>
          <Link to={`/topics/${item.topic.id}`}>{item.topic.name}</Link>
          <span>{topicTypeLabels[item.topic.topicType] ?? item.topic.topicType}</span>
        </div>
        <StanceBadge stance={item.currentStance} />
      </div>
      <p className="creator-topic-history-card__conclusion">{item.latestConclusion}</p>
      {item.latestEvidenceQuote ? <blockquote>“{item.latestEvidenceQuote}”</blockquote> : null}
      <div className="creator-topic-history-card__meta">
        <span>{item.opinionCount} 条观点</span>
        <span>{item.changeCount} 次变化</span>
        <span>{sourceLabels[item.currentSourceType] ?? item.currentSourceType}</span>
        <span>{horizonLabels[item.currentTimeHorizon] ?? item.currentTimeHorizon}</span>
        <span>{formatDate(item.latestPublishedAt)}</span>
      </div>
      <div className="creator-topic-history-card__actions">
        <Link to={`/topics/${item.topic.id}`}>查看主题历史</Link>
        <Link to={`/videos/${item.latestVideoId}`}>打开最新证据</Link>
      </div>
    </article>
  )
}

function ChangeCard({ change }: { change: CreatorIntelligenceChange }) {
  return (
    <article className="creator-change-card">
      <div className="creator-change-card__header">
        <Link to={`/topics/${change.topic.id}`}>{change.topic.name}</Link>
        <span>{changeLabels[change.changeType] ?? change.changeType}</span>
      </div>
      <div className="creator-change-card__stances">
        {change.previousStance ? <StanceBadge stance={change.previousStance} /> : <span>无历史立场</span>}
        <b>→</b>
        <StanceBadge stance={change.currentStance} />
      </div>
      <p>{change.changeSummary}</p>
      <div className="creator-change-card__footer">
        <time>{formatDate(change.detectedAt)}</time>
        <Link to={`/videos/${change.currentVideoId}`}>查看对应视频</Link>
      </div>
    </article>
  )
}

function OpinionCard({ opinion }: { opinion: CreatorTopicOpinion }) {
  return (
    <article className="creator-structured-opinion">
      <div className="creator-structured-opinion__header">
        <Link to={`/topics/${opinion.topic.id}`}>{opinion.topic.name}</Link>
        <StanceBadge stance={opinion.stance} />
      </div>
      <p>{opinion.conclusion}</p>
      {opinion.evidenceQuote ? <blockquote>“{opinion.evidenceQuote}”</blockquote> : null}
      <div className="creator-structured-opinion__meta">
        <span>{sourceLabels[opinion.sourceType] ?? opinion.sourceType}</span>
        <span>{horizonLabels[opinion.timeHorizon] ?? opinion.timeHorizon}</span>
        <span>{confidenceLabels[opinion.confidence] ?? opinion.confidence}</span>
        <time>{formatDate(opinion.publishedAt)}</time>
      </div>
      <Link className="creator-structured-opinion__source" to={`/videos/${opinion.videoId}`}>
        查看原始视频证据 →
      </Link>
    </article>
  )
}

export function CreatorIntelligencePanel({ secUid }: { secUid: string }) {
  const intelligence = useQuery({
    queryKey: ['creator-intelligence', secUid],
    queryFn: () => api.creatorIntelligence(secUid, 24, 12, 12),
    enabled: Boolean(secUid),
  })

  if (intelligence.isLoading) return <LoadingState label="正在读取结构化投资观点…" />
  if (intelligence.isError) {
    return <ErrorState error={intelligence.error} retry={() => { void intelligence.refetch() }} />
  }
  if (!intelligence.data) return null

  const data = intelligence.data
  if (!data.opinionCount) {
    return (
      <Panel title="投资观点历史" description="只统计已完成视频中的结构化财经观点。">
        <EmptyState
          title="暂无结构化投资观点"
          description="完成包含市场观点的视频分析后，这里会按标准主题建立历史。"
        />
      </Panel>
    )
  }

  const explicitRatio = Math.round(data.explicitCount / Math.max(1, data.opinionCount) * 100)
  return (
    <section className="creator-intelligence-section">
      <div className="creator-intelligence-heading">
        <div>
          <span>核心投资情报</span>
          <h2>博主历史观点</h2>
          <p>按标准主题汇总当前立场、历史变化和原始视频证据。</p>
        </div>
        <small>AI 推导与博主明确表达分开统计</small>
      </div>

      <div className="stats-grid creator-intelligence-stats">
        <StatCard label="投资主题" value={data.topicCount} hint="按标准主题去重" />
        <StatCard label="结构化观点" value={data.opinionCount} hint="仅统计完成状态视频" />
        <StatCard label="观点变化" value={data.changeCount} hint="转向、加强、减弱与重新关注" />
        <StatCard label="明确观点占比" value={`${explicitRatio}%`} hint={`${data.explicitCount} 明确 · ${data.inferredCount} 推导`} />
      </div>

      <div className="creator-intelligence-layout">
        <Panel title="主题立场与历史" description="当前立场取每个主题最近一条有效观点。">
          <div className="creator-topic-history-grid">
            {data.topics.map((item) => <TopicHistoryCard key={item.topic.id} item={item} />)}
          </div>
        </Panel>

        <Panel title="最近观点变化" description="变化记录由同一博主在同一主题下的历史观点计算。">
          {data.recentChanges.length ? (
            <div className="creator-change-list">
              {data.recentChanges.map((change) => <ChangeCard key={change.id} change={change} />)}
            </div>
          ) : (
            <EmptyState title="暂无观点变化" description="目前只有首次观点或立场保持不变。" />
          )}
        </Panel>
      </div>

      <Panel title="最近结构化观点" description="每条观点都可回到对应视频，不把 AI 推导当作博主原话。">
        <div className="creator-structured-opinion-grid">
          {data.recentOpinions.map((opinion) => <OpinionCard key={opinion.id} opinion={opinion} />)}
        </div>
      </Panel>
    </section>
  )
}
