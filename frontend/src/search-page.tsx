import { type FormEvent, type ReactNode, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatDate, formatDuration } from './api'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatusBadge,
  TagPills,
} from './components'
import type { SearchHit } from './types'
import './search-page.css'

const matchLabels: Record<string, string> = {
  transcript: '转写片段',
  key_point: '关键观点',
  summary: '摘要',
  description: '视频描述',
  tag: '标签',
  content: '内容',
}

function sourcePath(hit: SearchHit): string {
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

function SearchHitCard({ hit, query }: { hit: SearchHit; query: string }) {
  const timestamp = hit.match.start !== null
    ? `${formatDuration(hit.match.start)}${hit.match.end !== null ? ` – ${formatDuration(hit.match.end)}` : ''}`
    : null
  return (
    <Link className="search-hit-card" to={sourcePath(hit)}>
      <div className="search-hit-header">
        <div className="search-hit-badges">
          <StatusBadge status={hit.status} />
          <span className="match-type">{matchLabels[hit.match.matchType] ?? hit.match.matchType}</span>
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
        <strong>{timestamp ? '打开并播放命中片段 →' : '打开来源 →'}</strong>
      </div>
    </Link>
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

  function submit(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    if (q.trim()) next.set('q', q.trim())
    if (creator) next.set('creator', creator)
    if (tag) next.set('tag', tag)
    setParams(next)
  }

  return (
    <>
      <PageHeader
        eyebrow="来源检索"
        title="搜索知识内容"
        description="搜索描述、摘要、转写、标签和关键观点；命中转写时可直接跳到对应音频位置。"
      />
      <Panel className="search-hero">
        <form className="search-form search-form-expanded" onSubmit={submit}>
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
      {results.isError ? <ErrorState error={results.error} retry={() => { void results.refetch() }} /> : null}
      {results.data ? (
        <div className="page-stack">
          <div className="result-line">“{currentQuery}” 找到 <strong>{results.data.total}</strong> 条结果</div>
          {results.data.items.length ? (
            <div className="search-hit-list">
              {results.data.items.map((hit) => <SearchHitCard key={hit.id} hit={hit} query={currentQuery} />)}
            </div>
          ) : <EmptyState title="没有匹配内容" />}
        </div>
      ) : null}
    </>
  )
}
