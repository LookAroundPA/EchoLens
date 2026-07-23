import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatDate } from './api'
import { TopicAssetManager } from './topic-asset-manager'
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingState,
  PageHeader,
  Panel,
} from './components'
import type {
  TopicReviewItem,
  TopicStatusFilter,
  TopicType,
} from './types'
import './topic-management-page.css'

const topicTypeLabels: Record<string, string> = {
  stock: '股票',
  industry: '行业',
  index: '指数',
  commodity: '商品',
  currency: '汇率',
  macro: '宏观',
  market: '市场',
}

const topicTypes: Array<TopicType | ''> = [
  '',
  'stock',
  'industry',
  'index',
  'commodity',
  'currency',
  'macro',
  'market',
]

const statusLabels: Record<string, string> = {
  pending: '待审核',
  active: '已确认',
}

function TopicStatusBadge({ status }: { status: string }) {
  return (
    <span className={`topic-review-status topic-review-status--${status}`}>
      {statusLabels[status] ?? status}
    </span>
  )
}

function TopicReviewRow({
  item,
  selected,
  onSelect,
}: {
  item: TopicReviewItem
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`topic-review-row${selected ? ' is-selected' : ''}`}
      onClick={onSelect}
    >
      <div className="topic-review-row__main">
        <div className="topic-review-row__title">
          <strong>{item.topic.name}</strong>
          <TopicStatusBadge status={item.topic.status} />
          <span className="topic-type-chip">
            {topicTypeLabels[item.topic.topicType] ?? item.topic.topicType}
          </span>
        </div>
        <div className="topic-review-aliases">
          {item.aliases.slice(0, 5).map((alias) => <span key={alias}>{alias}</span>)}
          {item.aliases.length > 5 ? <span>+{item.aliases.length - 5}</span> : null}
        </div>
      </div>
      <div className="topic-review-row__metrics">
        <span><strong>{item.opinionCount}</strong> 观点</span>
        <span><strong>{item.creatorCount}</strong> 博主</span>
        <time>{formatDate(item.latestPublishedAt)}</time>
      </div>
    </button>
  )
}

export function TopicManagementPage() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const activeStatus = (params.get('status') as TopicStatusFilter | null) ?? 'pending'
  const activeType = (params.get('type') as TopicType | null) ?? ''
  const activeQuery = params.get('q') ?? ''
  const offset = Number(params.get('offset') ?? 0)
  const limit = 50

  const [q, setQ] = useState(activeQuery)
  const [status, setStatus] = useState<TopicStatusFilter>(activeStatus)
  const [topicType, setTopicType] = useState<TopicType | ''>(activeType)
  const [selected, setSelected] = useState<TopicReviewItem | null>(null)
  const [canonicalName, setCanonicalName] = useState('')
  const [reviewStatus, setReviewStatus] = useState<'active' | 'pending'>('pending')
  const [alias, setAlias] = useState('')
  const [targetQuery, setTargetQuery] = useState('')
  const [targetTopicId, setTargetTopicId] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const catalog = useQuery({
    queryKey: ['topic-review', activeStatus, activeType, activeQuery, offset],
    queryFn: () => api.topicReview({
      status: activeStatus,
      topicType: activeType || undefined,
      q: activeQuery || undefined,
      limit,
      offset,
    }),
  })

  const targetCatalog = useQuery({
    queryKey: ['topic-review-targets', selected?.topic.id, selected?.topic.topicType, targetQuery],
    queryFn: () => api.topicReview({
      status: 'active',
      topicType: selected?.topic.topicType as TopicType,
      q: targetQuery.trim() || undefined,
      limit: 200,
      offset: 0,
    }),
    enabled: Boolean(selected),
  })

  const mergeTargets = useMemo(
    () => targetCatalog.data?.items.filter((item) => item.topic.id !== selected?.topic.id) ?? [],
    [targetCatalog.data, selected?.topic.id],
  )

  useEffect(() => {
    if (!selected) return
    setCanonicalName(selected.topic.name)
    setReviewStatus(selected.topic.status === 'active' ? 'active' : 'pending')
    setAlias('')
    setTargetTopicId('')
    setTargetQuery('')
  }, [selected?.topic.id])

  const invalidateTopicData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['topic-review'] }),
      queryClient.invalidateQueries({ queryKey: ['topic-review-targets'] }),
      queryClient.invalidateQueries({ queryKey: ['topic-radar'] }),
      queryClient.invalidateQueries({ queryKey: ['topic'] }),
    ])
  }

  const updateTopic = useMutation({
    mutationFn: () => api.updateTopic(selected!.topic.id, {
      canonicalName: canonicalName.trim(),
      status: reviewStatus,
    }),
    onSuccess: async (item) => {
      setSelected(item)
      setSuccessMessage('主题名称和审核状态已更新。')
      await invalidateTopicData()
    },
  })

  const addAlias = useMutation({
    mutationFn: () => api.addTopicAlias(selected!.topic.id, { alias: alias.trim() }),
    onSuccess: async (item) => {
      setSelected(item)
      setAlias('')
      setSuccessMessage('别名已加入受控映射。后续相同表达将归入该主题。')
      await invalidateTopicData()
    },
  })

  const mergeTopic = useMutation({
    mutationFn: () => api.mergeTopic(selected!.topic.id, Number(targetTopicId)),
    onSuccess: async (result) => {
      setSelected(result.target)
      setTargetTopicId('')
      setSuccessMessage(
        `已迁移 ${result.movedOpinionCount} 条观点。源主题已归档，观点变化历史已重建。`,
      )
      await invalidateTopicData()
    },
  })

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    if (status !== 'pending') next.set('status', status)
    if (topicType) next.set('type', topicType)
    if (q.trim()) next.set('q', q.trim())
    setParams(next)
    setSelected(null)
    setSuccessMessage('')
  }

  function confirmMerge() {
    if (!selected || !targetTopicId) return
    const target = mergeTargets.find((item) => item.topic.id === Number(targetTopicId))
    if (!target) return
    const confirmed = window.confirm(
      `确认将“${selected.topic.name}”合并到“${target.topic.name}”？\n\n` +
      '源主题将归档，全部观点、别名和证据会迁移到目标主题。该操作不会删除原始视频。',
    )
    if (confirmed) mergeTopic.mutate()
  }

  return (
    <>
      <PageHeader
        eyebrow="主题治理"
        title="主题审核与合并"
        description="确认标准主题、维护精确别名，并将重复主题合并到受控目录。所有观点和原始视频证据都会保留。"
        actions={
          <>
            <Link className="button button-secondary" to="/">返回市场雷达</Link>
            <button className="button button-secondary" onClick={() => catalog.refetch()}>刷新目录</button>
          </>
        }
      />

      <Panel className="filter-panel">
        <form className="filter-bar filter-bar-wrap" onSubmit={applyFilters}>
          <label className="field grow">
            <span>主题或别名</span>
            <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="例如：AI、人工智能产业链" />
          </label>
          <label className="field">
            <span>审核状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value as TopicStatusFilter)}>
              <option value="pending">待审核</option>
              <option value="active">已确认</option>
              <option value="all">全部</option>
            </select>
          </label>
          <label className="field">
            <span>主题类型</span>
            <select value={topicType} onChange={(event) => setTopicType(event.target.value as TopicType | '')}>
              {topicTypes.map((value) => (
                <option key={value || 'all'} value={value}>
                  {value ? topicTypeLabels[value] : '全部类型'}
                </option>
              ))}
            </select>
          </label>
          <button className="button button-primary" type="submit">筛选</button>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => {
              setQ('')
              setStatus('pending')
              setTopicType('')
              setParams({})
              setSelected(null)
              setSuccessMessage('')
            }}
          >
            清空
          </button>
        </form>
      </Panel>

      {catalog.isLoading ? <LoadingState label="正在读取主题目录…" /> : null}
      {catalog.isError ? <ErrorState error={catalog.error} retry={() => catalog.refetch()} /> : null}

      {catalog.data ? (
        <div className="topic-management-layout">
          <Panel
            title={`${activeStatus === 'pending' ? '待审核主题' : '主题目录'} · ${catalog.data.total}`}
            description="按观点数量排序。选择一个主题后进行确认、别名维护或合并。"
            className="topic-review-list-panel"
          >
            {catalog.data.items.length ? (
              <div className="topic-review-list">
                {catalog.data.items.map((item) => (
                  <TopicReviewRow
                    key={item.topic.id}
                    item={item}
                    selected={selected?.topic.id === item.topic.id}
                    onSelect={() => {
                      setSuccessMessage('')
                      setSelected(item)
                    }}
                  />
                ))}
              </div>
            ) : (
              <EmptyState title="没有匹配主题" description="调整筛选条件或查看已确认主题。" />
            )}
            <div className="pagination topic-review-pagination">
              <button
                className="button button-secondary"
                disabled={offset <= 0}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  next.set('offset', String(Math.max(0, offset - limit)))
                  setParams(next)
                  setSelected(null)
                  setSuccessMessage('')
                }}
              >
                上一页
              </button>
              <span>第 {Math.floor(offset / limit) + 1} 页</span>
              <button
                className="button button-secondary"
                disabled={offset + limit >= catalog.data.total}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  next.set('offset', String(offset + limit))
                  setParams(next)
                  setSelected(null)
                  setSuccessMessage('')
                }}
              >
                下一页
              </button>
            </div>
          </Panel>

          <aside className="topic-management-editor">
            {!selected ? (
              <Panel>
                <EmptyState
                  title="选择一个主题"
                  description="审核前先查看原始别名、观点数量和关联博主，避免错误合并。"
                />
              </Panel>
            ) : (
              <div className="page-stack">
                <Panel
                  title={selected.topic.name}
                  description={`主题 ID ${selected.topic.id} · ${topicTypeLabels[selected.topic.topicType] ?? selected.topic.topicType}`}
                  action={<TopicStatusBadge status={selected.topic.status} />}
                >
                  <div className="topic-review-summary">
                    <div><span>观点</span><strong>{selected.opinionCount}</strong></div>
                    <div><span>博主</span><strong>{selected.creatorCount}</strong></div>
                    <div><span>最近出现</span><strong>{formatDate(selected.latestPublishedAt)}</strong></div>
                  </div>
                  <div className="topic-review-alias-cloud">
                    {selected.aliases.map((value) => <span key={value}>{value}</span>)}
                  </div>
                  <Link className="text-link" to={`/topics/${selected.topic.id}`}>查看观点与证据 →</Link>
                </Panel>

                <Panel title="确认标准主题" description="确认后会进入默认市场雷达。名称修改不会改变原始 raw_subject。">
                  <div className="form-stack">
                    <label className="field">
                      <span>标准名称</span>
                      <input value={canonicalName} onChange={(event) => setCanonicalName(event.target.value)} />
                    </label>
                    <label className="field">
                      <span>审核状态</span>
                      <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as 'active' | 'pending')}>
                        <option value="active">已确认</option>
                        <option value="pending">待审核</option>
                      </select>
                    </label>
                    <button
                      className="button button-primary full-width"
                      disabled={!canonicalName.trim() || updateTopic.isPending}
                      onClick={() => updateTopic.mutate()}
                    >
                      {updateTopic.isPending ? '正在保存…' : '保存主题'}
                    </button>
                    <InlineError error={updateTopic.error} />
                  </div>
                </Panel>

                <Panel title="添加受控别名" description="仅用于确定属于该主题的精确表达；存在冲突时应使用主题合并。">
                  <div className="topic-inline-form">
                    <input value={alias} onChange={(event) => setAlias(event.target.value)} placeholder="输入新别名" />
                    <button
                      className="button button-secondary"
                      disabled={!alias.trim() || addAlias.isPending}
                      onClick={() => addAlias.mutate()}
                    >
                      {addAlias.isPending ? '添加中…' : '添加别名'}
                    </button>
                  </div>
                  <InlineError error={addAlias.error} />
                </Panel>

                <TopicAssetManager
                  topicId={selected.topic.id}
                  topicStatus={selected.topic.status}
                />

                <Panel
                  title="合并重复主题"
                  description="只允许合并同类型主题。源主题会归档，观点、别名和证据迁移到目标主题。"
                  className="topic-merge-panel"
                >
                  <div className="form-stack">
                    <label className="field">
                      <span>搜索已确认目标主题</span>
                      <input
                        value={targetQuery}
                        onChange={(event) => setTargetQuery(event.target.value)}
                        placeholder="输入目标主题名称或别名"
                      />
                    </label>
                    <label className="field">
                      <span>合并到</span>
                      <select value={targetTopicId} onChange={(event) => setTargetTopicId(event.target.value)}>
                        <option value="">选择目标主题</option>
                        {mergeTargets.map((item) => (
                          <option key={item.topic.id} value={item.topic.id}>
                            {item.topic.name} · {item.opinionCount} 观点
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="topic-merge-warning">
                      合并是目录治理操作，不会删除视频，但源主题将不再单独展示。
                    </div>
                    <button
                      className="button topic-merge-button full-width"
                      disabled={!targetTopicId || mergeTopic.isPending}
                      onClick={confirmMerge}
                    >
                      {mergeTopic.isPending ? '正在合并…' : '合并到目标主题'}
                    </button>
                    <InlineError error={mergeTopic.error || targetCatalog.error} />
                  </div>
                </Panel>

                {successMessage ? <div className="topic-success-message">{successMessage}</div> : null}
              </div>
            )}
          </aside>
        </div>
      ) : null}
    </>
  )
}
