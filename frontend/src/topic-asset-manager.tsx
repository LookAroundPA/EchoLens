import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { EmptyState, InlineError, LoadingState, Panel } from './components'
import type {
  AssetRelationType,
  AssetType,
  ReferenceAsset,
  TopicAssetMapping,
} from './types'
import './topic-asset-manager.css'

const assetTypeLabels: Record<string, string> = {
  stock: '股票',
  etf: 'ETF',
  fund: '基金',
  index: '指数',
  industry: '行业',
  commodity: '商品',
  currency: '汇率',
}

const relationLabels: Record<string, string> = {
  direct: '核心相关',
  upstream: '上游',
  downstream: '下游',
  benchmark: '跟踪基准',
  related: '一般相关',
}

const assetTypes: AssetType[] = [
  'stock',
  'etf',
  'fund',
  'index',
  'industry',
  'commodity',
  'currency',
]

const relationTypes: AssetRelationType[] = [
  'direct',
  'benchmark',
  'upstream',
  'downstream',
  'related',
]

function assetDisplay(asset: ReferenceAsset): string {
  const market = asset.market ? `${asset.market}:` : ''
  return `${asset.name} · ${market}${asset.code}`
}

function AssetMappingRow({
  mapping,
  removable,
  onRemove,
  removing,
}: {
  mapping: TopicAssetMapping
  removable?: boolean
  onRemove?: () => void
  removing?: boolean
}) {
  return (
    <article className="reference-asset-row">
      <div className="reference-asset-row__main">
        <div className="reference-asset-row__title">
          <span className={`reference-asset-type reference-asset-type--${mapping.asset.assetType}`}>
            {assetTypeLabels[mapping.asset.assetType] ?? mapping.asset.assetType}
          </span>
          <strong>{mapping.asset.name}</strong>
          <span className="reference-asset-code">
            {mapping.asset.market ? `${mapping.asset.market}:` : ''}{mapping.asset.code}
          </span>
        </div>
        <div className="reference-asset-row__meta">
          <span>{relationLabels[mapping.relationType] ?? mapping.relationType}</span>
          <span>人工维护</span>
        </div>
        {mapping.note ? <p>{mapping.note}</p> : null}
      </div>
      {removable ? (
        <button
          type="button"
          className="reference-asset-remove"
          disabled={removing}
          onClick={onRemove}
        >
          {removing ? '移除中…' : '移除'}
        </button>
      ) : null}
    </article>
  )
}

export function TopicAssetReadOnly({ mappings }: { mappings: TopicAssetMapping[] }) {
  if (!mappings.length) {
    return (
      <EmptyState
        title="暂无参考标的"
        description="主题审核后可在主题管理中维护股票、ETF、基金或指数映射。"
      />
    )
  }
  return (
    <div className="reference-asset-list">
      {mappings.map((mapping) => <AssetMappingRow key={mapping.id} mapping={mapping} />)}
    </div>
  )
}

export function TopicAssetManager({
  topicId,
  topicStatus,
}: {
  topicId: number
  topicStatus: string
}) {
  const queryClient = useQueryClient()
  const [assetQuery, setAssetQuery] = useState('')
  const [assetType, setAssetType] = useState<AssetType>('stock')
  const [selectedAssetId, setSelectedAssetId] = useState('')
  const [relationType, setRelationType] = useState<AssetRelationType>('related')
  const [note, setNote] = useState('')
  const [newAssetType, setNewAssetType] = useState<AssetType>('stock')
  const [newAssetCode, setNewAssetCode] = useState('')
  const [newAssetName, setNewAssetName] = useState('')
  const [newAssetMarket, setNewAssetMarket] = useState('')
  const [message, setMessage] = useState('')

  const mappings = useQuery({
    queryKey: ['topic-assets', topicId],
    queryFn: () => api.topicAssets(topicId),
  })
  const catalog = useQuery({
    queryKey: ['reference-assets', assetType, assetQuery],
    queryFn: () => api.referenceAssets(assetType, assetQuery.trim() || undefined, 200, 0),
  })

  const availableAssets = useMemo(() => {
    const mappedIds = new Set(mappings.data?.items.map((item) => item.asset.id) ?? [])
    return catalog.data?.items.filter((item) => !mappedIds.has(item.id)) ?? []
  }, [catalog.data, mappings.data])

  useEffect(() => {
    setSelectedAssetId('')
    setMessage('')
  }, [topicId])

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['topic-assets', topicId] }),
      queryClient.invalidateQueries({ queryKey: ['reference-assets'] }),
      queryClient.invalidateQueries({ queryKey: ['topic', topicId] }),
    ])
  }

  const createAsset = useMutation({
    mutationFn: () => api.createReferenceAsset({
      assetType: newAssetType,
      code: newAssetCode.trim(),
      name: newAssetName.trim(),
      market: newAssetMarket.trim(),
    }),
    onSuccess: async (asset) => {
      setAssetType(asset.assetType as AssetType)
      setAssetQuery(asset.code)
      setSelectedAssetId(String(asset.id))
      setNewAssetCode('')
      setNewAssetName('')
      setNewAssetMarket('')
      setMessage('参考标的已加入目录，请确认关系后关联到当前主题。')
      await invalidate()
    },
  })

  const mapAsset = useMutation({
    mutationFn: () => api.mapTopicAsset(topicId, {
      assetId: Number(selectedAssetId),
      relationType,
      note: note.trim() || undefined,
    }),
    onSuccess: async () => {
      setSelectedAssetId('')
      setNote('')
      setMessage('参考标的关系已保存。该映射仅表示主题相关性。')
      await invalidate()
    },
  })

  const removeAsset = useMutation({
    mutationFn: (mappingId: number) => api.removeTopicAsset(topicId, mappingId),
    onSuccess: async () => {
      setMessage('参考标的关系已移除。')
      await invalidate()
    },
  })

  const active = topicStatus === 'active'

  return (
    <Panel
      title="相关标的（参考）"
      description="人工维护主题与股票、ETF、基金、指数等资产的相关性，仅供检索和信息整理，不构成买卖建议。"
      className="topic-asset-panel"
    >
      {mappings.isLoading ? <LoadingState label="正在读取参考标的…" /> : null}
      {mappings.data ? (
        mappings.data.items.length ? (
          <div className="reference-asset-list">
            {mappings.data.items.map((mapping) => (
              <AssetMappingRow
                key={mapping.id}
                mapping={mapping}
                removable={active}
                removing={removeAsset.isPending}
                onRemove={() => {
                  const confirmed = window.confirm(`确认移除“${mapping.asset.name}”与该主题的关联？`)
                  if (confirmed) removeAsset.mutate(mapping.id)
                }}
              />
            ))}
          </div>
        ) : <EmptyState title="尚未维护参考标的" />
      ) : null}

      {!active ? (
        <div className="topic-asset-review-notice">
          先将主题状态设为“已确认”，再维护参考标的，避免把未归一主题映射到资产。
        </div>
      ) : (
        <div className="topic-asset-editor-grid">
          <section className="topic-asset-editor-block">
            <div>
              <strong>关联已有标的</strong>
              <p>从受控资产目录中选择，不会自动抓取或推荐证券。</p>
            </div>
            <div className="topic-asset-search-row">
              <select value={assetType} onChange={(event) => setAssetType(event.target.value as AssetType)}>
                {assetTypes.map((value) => <option key={value} value={value}>{assetTypeLabels[value]}</option>)}
              </select>
              <input
                value={assetQuery}
                onChange={(event) => setAssetQuery(event.target.value)}
                placeholder="搜索代码、名称或市场"
              />
            </div>
            <label className="field">
              <span>参考标的</span>
              <select value={selectedAssetId} onChange={(event) => setSelectedAssetId(event.target.value)}>
                <option value="">选择标的</option>
                {availableAssets.map((asset) => (
                  <option key={asset.id} value={asset.id}>{assetDisplay(asset)}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>相关关系</span>
              <select value={relationType} onChange={(event) => setRelationType(event.target.value as AssetRelationType)}>
                {relationTypes.map((value) => <option key={value} value={value}>{relationLabels[value]}</option>)}
              </select>
            </label>
            <label className="field">
              <span>说明（可选）</span>
              <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} placeholder="说明为什么与该主题相关" />
            </label>
            <button
              type="button"
              className="button button-primary full-width"
              disabled={!selectedAssetId || mapAsset.isPending}
              onClick={() => mapAsset.mutate()}
            >
              {mapAsset.isPending ? '保存中…' : '保存关联'}
            </button>
          </section>

          <section className="topic-asset-editor-block">
            <div>
              <strong>新增资产目录项</strong>
              <p>代码、市场和类型共同确定唯一资产；重复提交会更新名称。</p>
            </div>
            <label className="field">
              <span>资产类型</span>
              <select value={newAssetType} onChange={(event) => setNewAssetType(event.target.value as AssetType)}>
                {assetTypes.map((value) => <option key={value} value={value}>{assetTypeLabels[value]}</option>)}
              </select>
            </label>
            <div className="topic-asset-code-row">
              <label className="field">
                <span>市场</span>
                <input value={newAssetMarket} onChange={(event) => setNewAssetMarket(event.target.value)} placeholder="例如 SH、SZ、HK" />
              </label>
              <label className="field">
                <span>代码</span>
                <input value={newAssetCode} onChange={(event) => setNewAssetCode(event.target.value)} placeholder="例如 588000" />
              </label>
            </div>
            <label className="field">
              <span>名称</span>
              <input value={newAssetName} onChange={(event) => setNewAssetName(event.target.value)} placeholder="例如 科创50ETF" />
            </label>
            <button
              type="button"
              className="button button-secondary full-width"
              disabled={!newAssetCode.trim() || !newAssetName.trim() || createAsset.isPending}
              onClick={() => createAsset.mutate()}
            >
              {createAsset.isPending ? '创建中…' : '加入资产目录'}
            </button>
          </section>
        </div>
      )}

      {message ? <div className="topic-success-message">{message}</div> : null}
      <InlineError error={mappings.error || catalog.error || createAsset.error || mapAsset.error || removeAsset.error} />
    </Panel>
  )
}
