import { type FormEvent, type ReactNode, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, formatDate, formatDuration } from './api'
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
import type { SemanticSearchHit } from './types'
import './search-page.css'

const sourceLabels: Record<string, string> = {
  transcript: '转写证据',
  analysis: '摘要与观点',
}

function sourcePath(hit: SemanticSearchHit): string {
  const params = new URLSearchParams()
  if (hit.match.start !== null) params.set('t', String(Math.max(0, hit.match.start)))
  if (hit.match.segmentIndex !== null) params.set('segment', String(hit.match.segmentIndex))
  const suffix = params.toString()
  return `/videos/${hit.id}${suffix ? `?${suffix}` : ''}`
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const normalizedQuery = query.trim()
  if (!normalizedQuery) return <>{text}</>
  const expression = new RegExp(`(${normalizedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig')
  const parts = text.split(expression)
  return (
    <>
      {parts.map((part, index): ReactNode => (
        part.toLocaleLowerCase() === normalizedQuery.toLocaleLowerCase()
          ? <mark key={`${index}-${part}`}>{part}</mark>
          : part
      ))}
    </>
  )
}

function SearchHitCard({ hit, query }: { hit: SemanticSearchHit; query: string }) {
  const timestamp = hit.match.start !== null
    ? `${formatDuration(hit.match.start)}${hit.match.end !== null ? ` – ${formatDuration(hit.match.end)}` : ''}`
    : null
  return (
    <Link className="search-hit-card" to={sourcePath(hit)}>
      <div className="search-hit-header">
        <div className="search-hit-badges">
          <StatusBadge status={hit.status} />
          <span className="match-type">{sourceLabels[hit.match.sourceType] ?? hit.match.sourceType}</span>
          <span className="semantic-score">相关度 {Math.round(hit.match.score * 100)}%</span>
          {timestamp ? <span className="match-time">▶ {timestamp}</span> : null}
        </div>
        <time>{formatDate(hit.publishedAt ?? hit.updatedAt)}</time>
      </div>
      <h2>{hit.description || hit.summary || `视频 ${hit.videoId}`}</h2>
      <blockquote>
        <HighlightedText text={hit.match.text || '匹配到该视频内容'} query={query} />
      </blockquote>
      <TagPills tags={hit.tags} max={6} />
      <div className="search-hit-footer">
        <span>{hit.creatorName || '未命名创作者'}</span>
        <strong>{timestamp ? '打开并播放相关片段 →' : '打开相关内容 →'}</strong>
      </div>
    </Link>
  )
}

export function SearchPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const currentQuery = params.get('q') ?? ''
  const currentCreator = params.get('creator') ?? ''
  const currentTag = params.get('tag') ?? ''
  const [q, setQ] = useState(currentQuery)
  const [tag, setTag] = useState(currentTag)
  const [creator, setCreator] = useState(currentCreator)
  const status = useQuery({
    queryKey: ['semantic-status'],
    queryFn: api.semanticStatus,
    refetchInterval: 20_000,
  })
  const results = useQuery({
    queryKey: ['semantic-search', currentQuery, currentCreator, currentTag],
    queryFn: () => api.semanticSearch(currentQuery, currentCreator || undefined, currentTag || undefined, 100),
    enabled: Boolean(currentQuery),
  })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => api.tags(undefined, 100) })
  const creators = useQuery({ queryKey: ['creators', 'search-filter'], queryFn: () => api.creators(undefined, 500) })
  const sync = useMutation({
    mutationFn: () => api.syncSemanticIndex({ rebuild: false }),
    onSuccess: (job) => navigate(`/jobs?focus=${job.id}`),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    if (q.trim()) next.set('q', q.trim())
    if (creator) next.set('creator', creator)
    if (tag) next.set('tag', tag)
    setParams(next)
  }

  const index = results.data?.index ?? status.data

  return (
    <>
      <PageHeader
        eyebrow="本地混合检索"
        title="搜索知识内容"
        description="同时使用本地中文语义向量和关键词匹配；结果保留视频、创作者与原始音频时间来源。"
        actions={(
          <button className="button button-secondary" onClick={() => sync.mutate()} disabled={sync.isPending}>
            {sync.isPending ? '正在提交…' : '同步语义索引'}
          </button>
        )}
      />
      <Panel className="semantic-index-strip">
        <div>
          <strong>{index?.ready ? '语义索引已就绪' : '语义索引尚未建立'}</strong>
          <span>
            {index?.model || '本地嵌入模型'} · {index?.videoCount ?? 0} 个视频 · {index?.chunkCount ?? 0} 个知识片段
          </span>
        </div>
        <small>{index?.autoSync ? '搜索时会自动增量同步新增和修改内容' : '需要手动同步索引'}</small>
      </Panel>
      <InlineError error={sync.error} />
      <Panel className="search-hero">
        <form className="search-form search-form-expanded" onSubmit={submit}>
          <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="例如：怎样减少重复工作、如何学习新技术" autoFocus />
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
      {!currentQuery ? <EmptyState title="输入自然语言开始搜索" description="不要求视频原文包含完全相同的关键词。" /> : null}
      {results.isLoading ? <LoadingState label="正在同步索引并检索相关片段…" /> : null}
      {results.isError ? <ErrorState error={results.error} retry={() => { void results.refetch() }} /> : null}
      {results.data ? (
        <div className="page-stack">
          <div className="result-line">“{currentQuery}” 返回 <strong>{results.data.total}</strong> 个相关来源</div>
          {results.data.items.length ? (
            <div className="search-hit-list">
              {results.data.items.map((hit) => <SearchHitCard key={`${hit.id}-${hit.match.sourceType}-${hit.match.segmentIndex ?? 'analysis'}`} hit={hit} query={currentQuery} />)}
            </div>
          ) : <EmptyState title="没有足够相关的内容" description="可以换一种表达，或先同步语义索引。" />}
        </div>
      ) : null}
    </>
  )
}
