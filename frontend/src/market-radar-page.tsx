import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, formatDate } from './api'
import { EmptyState, ErrorState, LoadingState, PageHeader, Panel, StatCard } from './components'
import type {
  DominantStance,
  MarketStance,
  TopicHeatMetrics,
  TopicOpinion,
  TopicOpinionChange,
  TopicRadarItem,
  TopicStatusFilter,
  TopicTrend,
  TopicTrendFilter,
  TopicType,
} from './types'
import './market-radar-page.css'

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
  mixed: '存在分歧',
}

const trendLabels: Record<TopicTrend, string> = {
  new: '新增关注',
  rising: '正在升温',
  stable: '热度稳定',
  falling: '明显降温',
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
  resumed_attention: '重新关注',
  strengthened: '立场加强',
  weakened: '立场减弱',
  bullish_reversal: '转为看多',
  bearish_reversal: '转为看空',
  turned_cautious: '转为谨慎',
  turned_neutral: '转为中性',
  turned_unclear: '转为不明确',
}

function stanceTone(stance: string): string {
  if (stance === 'strong_bullish' || stance === 'bullish') return 'bullish'
  if (stance === 'strong_bearish' || stance === 'bearish') return 'bearish'
  if (stance === 'cautious') return 'cautious'
  if (stance === 'neutral') return 'neutral'
  if (stance === 'mixed') return 'mixed'
  return 'unclear'
}

function StanceBadge({ stance }: { stance: string }) {
  return (
    <span className={`market-badge stance-badge stance-badge--${stanceTone(stance)}`}>
      {stanceLabels[stance] ?? stance}
    </span>
  )
}

function TrendBadge({ trend, change }: { trend: TopicTrend; change: number }) {
  const prefix = change > 0 ? '+' : ''
  return (
    <span className={`market-badge trend-badge trend-badge--${trend}`}>
      {trendLabels[trend]}{change ? ` ${prefix}${change.toFixed(1)}` : ''}
    </span>
  )
}

function TopicStatusBadge({ status }: { status: string }) {
  return (
    <span className={`market-badge topic-status topic-status--${status}`}>
      {status === 'active' ? '已确认主题' : status === 'pending' ? '待审核主题' : status}
    </span>
  )
}

function StanceDistribution({ metrics, compact = false }: { metrics: TopicHeatMetrics; compact?: boolean }) {
  const segments = [
    { key: 'bullish', label: '看多', ratio: metrics.bullishRatio },
    { key: 'cautious', label: '谨慎', ratio: metrics.cautiousRatio },
    { key: 'neutral', label: '中性', ratio: metrics.neutralRatio },
    { key: 'bearish', label: '看空', ratio: metrics.bearishRatio },
    { key: 'unclear', label: '不明确', ratio: metrics.unclearRatio },
  ].filter((item) => item.ratio > 0)

  if (!segments.length) return <span className="muted">暂无有效立场</span>

  return (
    <div className={`stance-distribution${compact ? ' stance-distribution--compact' : ''}`}>
      <div className="stance-track" aria-label="博主当前立场分布">
        {segments.map((item) => (
          <span
            key={item.key}
            className={`stance-segment stance-segment--${item.key}`}
            style={{ width: `${item.ratio * 100}%` }}
            title={`${item.label} ${Math.round(item.ratio * 100)}%`}
          />
        ))}
      </div>
      {!compact ? (
        <div className="stance-legend">
          {segments.map((item) => (
            <span key={item.key}>
              <i className={`stance-dot stance-dot--${item.key}`} />
              {item.label} {Math.round(item.ratio * 100)}%
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function TopicCard({ item, windowDays }: { item: TopicRadarItem; windowDays: 7 | 30 }) {
  const metrics = item.metrics
  return (
    <Link className="topic-card" to={`/topics/${item.topic.id}?window=${windowDays}`}>
      <div className="topic-card-head">
        <div className="topic-card-title">
          <span className="topic-type">{topicTypeLabels[item.topic.topicType] ?? item.topic.topicType}</span>
          <h3>{item.topic.name}</h3>
        </div>
        <TrendBadge trend={metrics.trend} change={metrics.heatChange} />
      </div>
      <div className="topic-card-score">
        <div>
          <span>热度</span>
          <strong>{metrics.heatScore.toFixed(1)}</strong>
        </div>
        <StanceBadge stance={metrics.dominantStance} />
      </div>
      <StanceDistribution metrics={metrics} compact />
      <div className="topic-card-metrics">
        <span><strong>{metrics.creatorCount}</strong> 位博主</span>
        <span><strong>{metrics.opinionCount}</strong> 条观点</span>
        <span><strong>{metrics.changeCount}</strong> 次变化</span>
      </div>
      <div className="topic-card-footer">
        <span>共识度 {Math.round(metrics.consensusRatio * 100)}%</span>
        <span>{formatDate(item.latestPublishedAt)}</span>
      </div>
    </Link>
  )
}

function TopicMiniList({
  title,
  description,
  items,
  windowDays,
  empty,
}: {
  title: string
  description: string
  items: TopicRadarItem[]
  windowDays: 7 | 30
  empty: string
}) {
  return (
    <Panel title={title} description={description}>
      {items.length ? (
        <div className="radar-mini-list">
          {items.map((item) => (
            <Link key={item.topic.id} to={`/topics/${item.topic.id}?window=${windowDays}`}>
              <div>
                <strong>{item.topic.name}</strong>
                <small>{item.metrics.creatorCount} 位博主 · {item.metrics.opinionCount} 条观点</small>
              </div>
              <div className="radar-mini-value">
                <span className={`heat-change heat-change--${item.metrics.heatChange >= 0 ? 'up' : 'down'}`}>
                  {item.metrics.heatChange > 0 ? '+' : ''}{item.metrics.heatChange.toFixed(1)}
                </span>
                <StanceBadge stance={item.metrics.dominantStance} />
              </div>
            </Link>
          ))}
        </div>
      ) : <EmptyState title={empty} />}
    </Panel>
  )
}

function setSearchParam(
  params: URLSearchParams,
  setParams: (nextInit: URLSearchParams) => void,
  key: string,
  value: string,
  defaultValue?: string,
) {
  const next = new URLSearchParams(params)
  if (!value || value === defaultValue) next.delete(key)
  else next.set(key, value)
  setParams(next)
}

export function MarketRadarPage() {
  const [params, setParams] = useSearchParams()
  const windowDays: 7 | 30 = params.get('window') === '30' ? 30 : 7
  const status = (params.get('status') ?? 'all') as TopicStatusFilter
  const topicType = (params.get('type') || undefined) as TopicType | undefined
  const trend = (params.get('trend') ?? 'all') as TopicTrendFilter

  const radar = useQuery({
    queryKey: ['topic-radar', windowDays, status, topicType],
    queryFn: () => api.topicRadar({ windowDays, status, topicType, trend: 'all', limit: 200 }),
  })

  const allItems = radar.data?.items ?? []
  const items = allItems
    .filter((item) => trend === 'all' || item.metrics.trend === trend)
    .sort((left, right) => {
      if (trend === 'falling') return left.metrics.heatChange - right.metrics.heatChange
      if (trend === 'rising') return right.metrics.heatChange - left.metrics.heatChange
      return right.metrics.heatScore - left.metrics.heatScore
    })

  const totalOpinions = allItems.reduce((sum, item) => sum + item.metrics.opinionCount, 0)
  const totalChanges = allItems.reduce((sum, item) => sum + item.metrics.changeCount, 0)
  const explicitCount = allItems.reduce((sum, item) => sum + item.metrics.explicitCount, 0)
  const inferredCount = allItems.reduce((sum, item) => sum + item.metrics.inferredCount, 0)
  const explicitRatio = explicitCount + inferredCount ? explicitCount / (explicitCount + inferredCount) : 0

  const rising = allItems
    .filter((item) => item.metrics.trend === 'rising' || item.metrics.trend === 'new')
    .sort((left, right) => right.metrics.heatChange - left.metrics.heatChange)
    .slice(0, 6)
  const falling = allItems
    .filter((item) => item.metrics.trend === 'falling')
    .sort((left, right) => left.metrics.heatChange - right.metrics.heatChange)
    .slice(0, 6)
  const consensus = allItems
    .filter((item) => item.metrics.creatorCount >= 2 && item.metrics.consensusRatio >= 0.6)
    .sort((left, right) => right.metrics.consensusRatio - left.metrics.consensusRatio || right.metrics.creatorCount - left.metrics.creatorCount)
    .slice(0, 6)
  const disagreement = allItems
    .filter((item) => item.metrics.creatorCount >= 2 && (item.metrics.dominantStance === 'mixed' || item.metrics.consensusRatio < 0.5))
    .sort((left, right) => right.metrics.creatorCount - left.metrics.creatorCount || right.metrics.heatScore - left.metrics.heatScore)
    .slice(0, 6)

  return (
    <>
      <PageHeader
        eyebrow="投资情报"
        title="市场雷达"
        description={`聚合财经博主最近 ${windowDays} 日观点，观察主题热度、立场变化、共识与分歧。所有结论均可追溯到视频证据。`}
        actions={
          <div className="window-switch" aria-label="统计周期">
            <button
              type="button"
              className={windowDays === 7 ? 'is-active' : ''}
              onClick={() => setSearchParam(params, setParams, 'window', '7', '7')}
            >7 日</button>
            <button
              type="button"
              className={windowDays === 30 ? 'is-active' : ''}
              onClick={() => setSearchParam(params, setParams, 'window', '30', '7')}
            >30 日</button>
          </div>
        }
      />

      <Panel className="filter-panel radar-filter-panel">
        <div className="filter-bar filter-bar-wrap">
          <label className="field">
            <span>主题状态</span>
            <select
              value={status}
              onChange={(event) => setSearchParam(params, setParams, 'status', event.target.value, 'all')}
            >
              <option value="all">全部主题</option>
              <option value="active">已确认</option>
              <option value="pending">待审核</option>
            </select>
          </label>
          <label className="field">
            <span>主题类型</span>
            <select
              value={topicType ?? ''}
              onChange={(event) => setSearchParam(params, setParams, 'type', event.target.value)}
            >
              <option value="">全部类型</option>
              {Object.entries(topicTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>热度趋势</span>
            <select
              value={trend}
              onChange={(event) => setSearchParam(params, setParams, 'trend', event.target.value, 'all')}
            >
              <option value="all">全部趋势</option>
              <option value="new">新增关注</option>
              <option value="rising">正在升温</option>
              <option value="stable">热度稳定</option>
              <option value="falling">明显降温</option>
            </select>
          </label>
          <button className="button button-secondary" type="button" onClick={() => radar.refetch()}>
            刷新雷达
          </button>
        </div>
      </Panel>

      {radar.isLoading ? <LoadingState label="正在计算市场雷达…" /> : null}
      {radar.isError ? <ErrorState error={radar.error} retry={() => radar.refetch()} /> : null}
      {radar.data ? (
        <div className="page-stack radar-page-stack">
          <section className="stats-grid radar-stats-grid">
            <StatCard label="雷达主题" value={allItems.length} hint="进入本期或上一周期统计" />
            <StatCard label="结构化观点" value={totalOpinions} hint="已去除无观点视频" />
            <StatCard label="观点变化" value={totalChanges} hint="首次关注、转向与强弱变化" />
            <StatCard label="明确观点占比" value={`${Math.round(explicitRatio * 100)}%`} hint="博主明确表达 / 全部观点" />
          </section>

          <div className="two-column-grid radar-signal-grid">
            <TopicMiniList
              title="正在升温"
              description="与上一等长周期相比热度提升最大"
              items={rising}
              windowDays={windowDays}
              empty="本期暂无明显升温主题"
            />
            <TopicMiniList
              title="明显降温"
              description="当前关注减少或已经停止讨论"
              items={falling}
              windowDays={windowDays}
              empty="本期暂无明显降温主题"
            />
            <TopicMiniList
              title="多博主共识"
              description="至少两位博主参与，且主导立场较集中"
              items={consensus}
              windowDays={windowDays}
              empty="暂未形成明显共识"
            />
            <TopicMiniList
              title="观点分歧"
              description="多博主参与，但当前立场差异较大"
              items={disagreement}
              windowDays={windowDays}
              empty="暂未发现明显分歧"
            />
          </div>

          <Panel
            title="主题热度排行"
            description={`当前显示 ${items.length} 个主题；热度由独立博主、降权后的提及和观点变化共同构成。`}
            action={<span className="radar-generated">更新于 {formatDate(radar.data.generatedAt)}</span>}
          >
            {items.length ? (
              <div className="topic-grid">
                {items.map((item) => <TopicCard key={item.topic.id} item={item} windowDays={windowDays} />)}
              </div>
            ) : <EmptyState title="没有符合条件的主题" description="调整主题状态、类型或趋势筛选。" />}
          </Panel>
        </div>
      ) : null}
    </>
  )
}

function OpinionCard({ opinion }: { opinion: TopicOpinion }) {
  return (
    <article className="opinion-card">
      <div className="opinion-card-head">
        <div>
          <Link to={`/creators/${encodeURIComponent(opinion.creatorSecUid)}`} className="opinion-creator">
            {opinion.creatorName || opinion.creatorSecUid}
          </Link>
          <time>{formatDate(opinion.publishedAt)}</time>
        </div>
        <div className="opinion-badges">
          <StanceBadge stance={opinion.stance} />
          <span className={`market-badge source-badge source-badge--${opinion.sourceType}`}>
            {sourceLabels[opinion.sourceType] ?? opinion.sourceType}
          </span>
        </div>
      </div>
      <h3>{opinion.conclusion}</h3>
      <div className="opinion-meta">
        <span>原始主题：{opinion.rawSubject}</span>
        <span>{horizonLabels[opinion.timeHorizon] ?? opinion.timeHorizon}</span>
        <span>{confidenceLabels[opinion.confidence] ?? opinion.confidence}</span>
      </div>
      {opinion.evidenceQuote ? (
        <blockquote>“{opinion.evidenceQuote}”</blockquote>
      ) : null}
      {opinion.reasoning.length ? (
        <div className="opinion-list opinion-list--reasoning">
          <strong>判断依据</strong>
          <ul>{opinion.reasoning.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
      {opinion.risks.length ? (
        <div className="opinion-list opinion-list--risks">
          <strong>主要风险</strong>
          <ul>{opinion.risks.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
      <div className="opinion-card-footer">
        {opinion.changeType ? (
          <span className="opinion-change-note">
            {changeLabels[opinion.changeType] ?? opinion.changeType}
            {opinion.changeSummary ? `：${opinion.changeSummary}` : ''}
          </span>
        ) : <span />}
        <Link className="text-link" to={`/videos/${opinion.videoId}`}>查看原始视频 →</Link>
      </div>
    </article>
  )
}

function ChangeCard({ change }: { change: TopicOpinionChange }) {
  return (
    <Link className="change-card" to={`/videos/${change.currentVideoId}`}>
      <div className="change-card-head">
        <strong>{change.creatorName || change.creatorSecUid}</strong>
        <time>{formatDate(change.detectedAt)}</time>
      </div>
      <div className="change-transition">
        {change.previousStance ? <StanceBadge stance={change.previousStance} /> : <span className="market-badge">无历史观点</span>}
        <span>→</span>
        <StanceBadge stance={change.currentStance} />
      </div>
      <p>{change.changeSummary}</p>
      <span className="change-type-label">{changeLabels[change.changeType] ?? change.changeType}</span>
    </Link>
  )
}

function HeatBreakdown({ metrics }: { metrics: TopicHeatMetrics }) {
  const components = [
    { key: 'creator_score', label: '独立博主', hint: '每位博主提供更高权重' },
    { key: 'mention_score', label: '有效提及', hint: '同一博主同日重复发布已降权' },
    { key: 'change_score', label: '观点变化', hint: '转向、加强和首次关注' },
  ]
  const total = Math.max(metrics.heatScore, 1)
  return (
    <div className="heat-breakdown">
      {components.map((item) => {
        const value = metrics.heatComponents[item.key] ?? 0
        return (
          <div key={item.key}>
            <div className="heat-breakdown-label">
              <span>{item.label}<small>{item.hint}</small></span>
              <strong>{value.toFixed(1)}</strong>
            </div>
            <div className="heat-component-track"><span style={{ width: `${Math.min(100, value / total * 100)}%` }} /></div>
          </div>
        )
      })}
    </div>
  )
}

export function TopicDetailPage() {
  const { id } = useParams()
  const topicId = Number(id)
  const [params, setParams] = useSearchParams()
  const windowDays: 7 | 30 = params.get('window') === '7' ? 7 : 30
  const offset = Math.max(0, Number(params.get('offset') ?? 0) || 0)
  const limit = 20

  const detail = useQuery({
    queryKey: ['topic', topicId, windowDays],
    queryFn: () => api.topic(topicId, windowDays, 12),
    enabled: Number.isFinite(topicId),
  })
  const history = useQuery({
    queryKey: ['topic-history', topicId, offset],
    queryFn: () => api.topicHistory(topicId, undefined, limit, offset),
    enabled: Number.isFinite(topicId),
  })

  if (!Number.isFinite(topicId)) return <ErrorState error={new Error('无效的主题 ID')} />
  if (detail.isLoading || history.isLoading) return <LoadingState label="正在读取主题投资情报…" />
  if (detail.isError) return <ErrorState error={detail.error} retry={() => detail.refetch()} />
  if (history.isError) return <ErrorState error={history.error} retry={() => history.refetch()} />
  if (!detail.data || !history.data) return null

  const data = detail.data
  const metrics = data.metrics
  return (
    <>
      <PageHeader
        eyebrow={`${topicTypeLabels[data.topic.topicType] ?? data.topic.topicType}主题`}
        title={data.topic.name}
        description={`追踪不同博主对该主题的历史观点、当前共识、观点变化与原始视频证据。统计周期为最近 ${windowDays} 日。`}
        actions={
          <>
            <div className="window-switch" aria-label="统计周期">
              <button
                type="button"
                className={windowDays === 7 ? 'is-active' : ''}
                onClick={() => setSearchParam(params, setParams, 'window', '7', '30')}
              >7 日</button>
              <button
                type="button"
                className={windowDays === 30 ? 'is-active' : ''}
                onClick={() => setSearchParam(params, setParams, 'window', '30', '30')}
              >30 日</button>
            </div>
            <Link className="button button-secondary" to={`/?window=${windowDays}`}>返回市场雷达</Link>
          </>
        }
      />

      <section className="stats-grid topic-detail-stats">
        <StatCard label="当前热度" value={metrics.heatScore.toFixed(1)} hint={`上期 ${metrics.previousHeatScore.toFixed(1)}`} />
        <StatCard label="参与博主" value={metrics.creatorCount} hint="每位博主仅贡献一个当前立场" />
        <StatCard label="观点数量" value={metrics.opinionCount} hint={`${metrics.explicitCount} 明确 · ${metrics.inferredCount} 推导`} />
        <StatCard label="观点变化" value={metrics.changeCount} hint={trendLabels[metrics.trend]} />
      </section>

      <div className="topic-detail-layout">
        <main className="page-stack">
          <Panel
            title="最新观点"
            description="优先展示最近发布的观点；红色表示看多，绿色表示看空。"
            action={<TrendBadge trend={metrics.trend} change={metrics.heatChange} />}
          >
            {data.latestOpinions.length ? (
              <div className="opinion-list-grid">
                {data.latestOpinions.map((opinion) => <OpinionCard key={opinion.id} opinion={opinion} />)}
              </div>
            ) : <EmptyState title="本期暂无观点" description="可在下方历史记录中查看之前的讨论。" />}
          </Panel>

          <Panel title="观点变化" description="观点变化比单次观点更值得关注。">
            {data.recentChanges.length ? (
              <div className="change-grid">
                {data.recentChanges.map((change) => <ChangeCard key={change.id} change={change} />)}
              </div>
            ) : <EmptyState title="暂无观点变化" description="目前没有识别到转向、加强、减弱或重新关注。" />}
          </Panel>

          <Panel title="完整观点历史" description={`共 ${history.data.total} 条结构化观点，可追溯到具体视频。`}>
            {history.data.items.length ? (
              <div className="opinion-list-grid">
                {history.data.items.map((opinion) => <OpinionCard key={opinion.id} opinion={opinion} />)}
              </div>
            ) : <EmptyState title="暂无历史观点" />}
            {history.data.total > limit ? (
              <div className="pagination topic-history-pagination">
                <button
                  className="button button-secondary"
                  disabled={offset <= 0}
                  onClick={() => setSearchParam(params, setParams, 'offset', String(Math.max(0, offset - limit)), '0')}
                >上一页</button>
                <span>第 {Math.floor(offset / limit) + 1} 页</span>
                <button
                  className="button button-secondary"
                  disabled={offset + limit >= history.data.total}
                  onClick={() => setSearchParam(params, setParams, 'offset', String(offset + limit), '0')}
                >下一页</button>
              </div>
            ) : null}
          </Panel>
        </main>

        <aside className="page-stack topic-detail-aside">
          <Panel title="当前判断">
            <div className="topic-current-view">
              <div className="topic-current-top">
                <StanceBadge stance={metrics.dominantStance as DominantStance} />
                <TopicStatusBadge status={data.topic.status} />
              </div>
              <StanceDistribution metrics={metrics} />
              <dl className="topic-metric-list">
                <div><dt>共识度</dt><dd>{Math.round(metrics.consensusRatio * 100)}%</dd></div>
                <div><dt>明确观点</dt><dd>{metrics.explicitCount}</dd></div>
                <div><dt>AI 推导</dt><dd>{metrics.inferredCount}</dd></div>
                <div><dt>降权后提及</dt><dd>{metrics.weightedMentions.toFixed(1)}</dd></div>
              </dl>
            </div>
          </Panel>

          <Panel title="热度构成" description="热度只用于解释关注变化，不代表投资收益。">
            <HeatBreakdown metrics={metrics} />
          </Panel>

          <Panel title="主题别名" description="不同表达统一归入此标准主题。">
            {data.aliases.length ? (
              <div className="topic-aliases">
                {data.aliases.map((alias) => <span key={alias}>{alias}</span>)}
              </div>
            ) : <span className="muted">暂无别名</span>}
          </Panel>

          <Panel title="信息边界">
            <div className="boundary-note">
              <p><strong>博主明确观点</strong>来自原始视频中的直接表达。</p>
              <p><strong>AI 推导</strong>是系统根据上下文形成的结构化判断。</p>
              <p>相关内容仅用于信息整理和决策辅助，不构成买卖建议。</p>
            </div>
          </Panel>
        </aside>
      </div>
    </>
  )
}
