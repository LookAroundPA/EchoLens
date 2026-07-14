import { type FormEvent, type ReactNode, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, formatDate, formatDuration } from './api'
import {
  EmptyState,
  ErrorState,
  InlineError,
  PageHeader,
  Panel,
} from './components'
import type { KnowledgeSource } from './types'
import './knowledge-page.css'

function sourcePath(source: KnowledgeSource): string {
  const params = new URLSearchParams()
  if (source.start !== null) params.set('t', String(Math.max(0, source.start)))
  if (source.segmentIndex !== null) params.set('segment', String(source.segmentIndex))
  const suffix = params.toString()
  return `/videos/${source.videoId}${suffix ? `?${suffix}` : ''}`
}

function AnswerWithCitations({ answer, sources }: { answer: string; sources: KnowledgeSource[] }) {
  const sourceById = useMemo(
    () => new Map(sources.map((source) => [source.sourceId, source])),
    [sources],
  )
  const parts = answer.split(/(\[S\d+\])/g)
  return (
    <div className="knowledge-answer-text">
      {parts.map((part, index): ReactNode => {
        const match = /^\[(S\d+)\]$/.exec(part)
        if (!match) return <span key={`${index}-${part}`}>{part}</span>
        const source = sourceById.get(match[1])
        if (!source) return <span key={`${index}-${part}`}>{part}</span>
        return (
          <Link
            key={`${index}-${part}`}
            className="answer-citation"
            to={sourcePath(source)}
            title={source.title}
          >
            {part}
          </Link>
        )
      })}
    </div>
  )
}

function SourceCard({ source }: { source: KnowledgeSource }) {
  const timestamp = source.start !== null
    ? `${formatDuration(source.start)}${source.end !== null ? ` – ${formatDuration(source.end)}` : ''}`
    : null
  return (
    <Link className="knowledge-source-card" to={sourcePath(source)}>
      <div className="knowledge-source-heading">
        <span>{source.sourceId}</span>
        <div>
          <strong>{source.title}</strong>
          <small>{source.creatorName || source.creatorSecUid} · {formatDate(source.publishedAt)}</small>
        </div>
      </div>
      <p>{source.text}</p>
      <div className="knowledge-source-footer">
        <span>相关度 {Math.round(source.score * 100)}%</span>
        <strong>{timestamp ? `▶ ${timestamp} 打开证据` : '打开视频来源 →'}</strong>
      </div>
    </Link>
  )
}

export function KnowledgePage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const initialQuestion = params.get('q') ?? ''
  const [question, setQuestion] = useState(initialQuestion)
  const [creator, setCreator] = useState(params.get('creator') ?? '')
  const [tag, setTag] = useState(params.get('tag') ?? '')
  const [thinking, setThinking] = useState(false)
  const [maxSources, setMaxSources] = useState(8)

  const status = useQuery({
    queryKey: ['semantic-status'],
    queryFn: api.semanticStatus,
    refetchInterval: 20_000,
  })
  const creators = useQuery({
    queryKey: ['creators', 'qa-filter'],
    queryFn: () => api.creators(undefined, 500),
  })
  const tags = useQuery({
    queryKey: ['tags'],
    queryFn: () => api.tags(undefined, 100),
  })
  const sync = useMutation({
    mutationFn: (rebuild: boolean) => api.syncSemanticIndex({ rebuild }),
    onSuccess: (job) => navigate(`/jobs?focus=${job.id}`),
  })
  const ask = useMutation({
    mutationFn: () => api.ask({
      question: question.trim(),
      creatorSecUid: creator || undefined,
      tag: tag || undefined,
      maxSources,
      thinking,
    }),
    onSuccess: () => {
      const next = new URLSearchParams()
      if (question.trim()) next.set('q', question.trim())
      if (creator) next.set('creator', creator)
      if (tag) next.set('tag', tag)
      setParams(next, { replace: true })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!question.trim()) return
    ask.mutate()
  }

  return (
    <>
      <PageHeader
        eyebrow="有来源的跨视频问答"
        title="向内容库提问"
        description="先在本地检索相关视频片段，再由 DeepSeek V4 Pro 仅依据这些证据组织回答。每个引用都可以回到原音频。"
        actions={(
          <button
            className="button button-secondary"
            onClick={() => sync.mutate(false)}
            disabled={sync.isPending}
          >
            {sync.isPending ? '正在提交…' : '同步语义索引'}
          </button>
        )}
      />

      <Panel className="knowledge-index-panel">
        {status.isError ? <ErrorState error={status.error} retry={() => { void status.refetch() }} /> : (
          <div className="knowledge-index-status">
            <div>
              <strong>{status.data?.ready ? '本地知识索引已就绪' : '首次使用前需要建立索引'}</strong>
              <span>
                {status.data?.model || 'BAAI/bge-small-zh-v1.5'} · {status.data?.videoCount ?? 0} 个视频 · {status.data?.chunkCount ?? 0} 个片段
              </span>
            </div>
            <button
              className="text-link index-rebuild-button"
              onClick={() => {
                if (window.confirm('完全重建会重新计算全部本地向量，确认继续？')) sync.mutate(true)
              }}
              disabled={sync.isPending}
            >
              完全重建
            </button>
          </div>
        )}
      </Panel>
      <InlineError error={sync.error} />

      <Panel className="knowledge-question-panel">
        <form className="knowledge-question-form" onSubmit={submit}>
          <label className="field knowledge-question-field">
            <span>问题</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="例如：这些视频对提高工作效率有哪些共同建议？不同创作者有哪些分歧？"
              autoFocus
            />
          </label>
          <div className="knowledge-question-options">
            <label className="field">
              <span>限定创作者</span>
              <select value={creator} onChange={(event) => setCreator(event.target.value)}>
                <option value="">全部创作者</option>
                {creators.data?.items.map((item) => (
                  <option key={item.secUid} value={item.secUid}>{item.name || item.secUid}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>限定标签</span>
              <select value={tag} onChange={(event) => setTag(event.target.value)}>
                <option value="">全部标签</option>
                {tags.data?.items.map((item) => <option key={item.tag} value={item.tag}>{item.tag}</option>)}
              </select>
            </label>
            <label className="field">
              <span>最多来源</span>
              <select value={maxSources} onChange={(event) => setMaxSources(Number(event.target.value))}>
                <option value={6}>6 个</option>
                <option value={8}>8 个</option>
                <option value={12}>12 个</option>
                <option value={16}>16 个</option>
              </select>
            </label>
          </div>
          <label className="check-field knowledge-thinking-option">
            <input type="checkbox" checked={thinking} onChange={(event) => setThinking(event.target.checked)} />
            使用 V4 Pro 深度思考模式（更适合比较、归纳和复杂问题）
          </label>
          <div className="knowledge-question-actions">
            <button className="button button-primary" disabled={ask.isPending || !question.trim()}>
              {ask.isPending ? '正在检索并生成回答…' : '开始提问'}
            </button>
            <Link className="button button-secondary" to={`/search${question.trim() ? `?q=${encodeURIComponent(question.trim())}` : ''}`}>
              只查看搜索结果
            </Link>
          </div>
          <InlineError error={ask.error} />
        </form>
      </Panel>

      {ask.data ? (
        <div className="page-stack knowledge-result-stack">
          <Panel
            title={ask.data.insufficientEvidence ? '证据不足' : '基于视频证据的回答'}
            description={`${ask.data.model || '未调用模型'} · ${ask.data.thinking ? '深度思考' : '普通模式'} · ${ask.data.sources.length} 个检索来源`}
            className={ask.data.insufficientEvidence ? 'knowledge-answer-panel is-insufficient' : 'knowledge-answer-panel'}
          >
            <AnswerWithCitations answer={ask.data.answer} sources={ask.data.sources} />
          </Panel>

          <Panel title={`引用来源 · ${ask.data.sources.length}`} description="点击来源可直接定位到原始视频和音频时间点。">
            {ask.data.sources.length ? (
              <div className="knowledge-source-grid">
                {ask.data.sources.map((source) => <SourceCard key={source.sourceId} source={source} />)}
              </div>
            ) : <EmptyState title="没有检索到可用来源" description="换一种表达、扩大范围，或先同步索引。" />}
          </Panel>
        </div>
      ) : (
        <EmptyState title="提出一个需要跨视频整理的问题" description="回答只使用本地内容库中的证据，不会联网补充事实。" />
      )}
    </>
  )
}
