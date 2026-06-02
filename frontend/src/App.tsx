import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE

function getPdfUrl(source: string): string | null {
  const normalized = source.replace(/\\/g, '/')
  const match = normalized.match(/data\/(.+\.pdf)$/i)
  return match ? `${API_BASE}/pdfs/${match[1]}` : null
}

// ── Types ──────────────────────────────────────────────────────────────────
interface ContextDoc {
  page_content: string
  metadata: Record<string, unknown>
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  context?: ContextDoc[]
  extractedYears?: number[]
  streaming?: boolean   // true while tokens are still arriving
  error?: boolean
}

// ── Types ──────────────────────────────────────────────────────────────────
interface Stock {
  ticker: string
  name: string
  sector: string
  subsector: string
}

// ── Prompt suggestions ─────────────────────────────────────────────────────
const SUGGESTIONS = [
  { icon: '🏦', label: 'Total Aset BBRI 2025', text: 'Berapa total aset BBRI per 31 Desember 2025?' },
  { icon: '📈', label: 'ROE BBCA 2025', text: 'Berapa ROE BBCA untuk tahun 2025?' },
  { icon: '📊', label: 'Tren Laba BMRI', text: 'Bagaimana tren pertumbuhan laba bersih BMRI dari 2022 hingga 2025?' },
  { icon: '🛡️', label: 'Keamanan Bank BBCA', text: 'Analisis rasio CAR, NPL, dan LDR BBCA — seberapa aman bank ini?' },
]

// ── Source docs accordion ──────────────────────────────────────────────────
function SourceDocs({ docs }: { docs: ContextDoc[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="sources">
      <button className="sources-toggle" onClick={() => setOpen(o => !o)}>
        <span className="sources-icon">📄</span>
        {docs.length} source{docs.length !== 1 ? 's' : ''}
        <span className="sources-chevron">{open ? '▴' : '▾'}</span>
      </button>
      {open && (
        <div className="sources-list">
          {docs.map((doc, i) => (
            <div key={i} className="source-item">
              <div className="source-item-header">
                <span className="source-badge">{i + 1}</span>
                {doc.metadata?.source != null && (
                  <span className="source-meta">
                    {String(doc.metadata.source).replace(/\\/g, '/').split('/').pop()}
                  </span>
                )}
                {doc.metadata?.source != null && getPdfUrl(String(doc.metadata.source)) && (
                  <a
                    className="source-pdf-link"
                    href={getPdfUrl(String(doc.metadata.source))!}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open PDF ↗
                  </a>
                )}
              </div>
              <p className="source-text">
                {doc.page_content.length > 400
                  ? doc.page_content.slice(0, 400) + '…'
                  : doc.page_content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Individual chat bubble ──────────────────────────────────────────────────
function MessageBubble({
  msg,
  showContext,
}: {
  msg: Message
  showContext: boolean
}) {
  if (msg.role === 'user') {
    return (
      <div className="msg msg--user">
        <div className="bubble bubble--user">{msg.content}</div>
      </div>
    )
  }

  // While the assistant placeholder is empty and still streaming, show dots
  const showDots = msg.streaming && msg.content === ''

  return (
    <div className="msg msg--assistant">
      <div className="assistant-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div className="assistant-body">
        {showDots ? (
          <div className="typing-dots"><span /><span /><span /></div>
        ) : (
          <div className={`prose${msg.error ? ' prose--error' : ''}`}>
            <ReactMarkdown>{msg.content}</ReactMarkdown>
            {msg.streaming && <span className="cursor-blink" />}
          </div>
        )}
        {!msg.streaming && msg.extractedYears && msg.extractedYears.length > 0 && (
          <div className="year-pills">
            {msg.extractedYears.map(y => (
              <span key={y} className="year-pill">📅 {y}</span>
            ))}
          </div>
        )}
        {!msg.streaming && showContext && msg.context && msg.context.length > 0 && (
          <SourceDocs docs={msg.context} />
        )}
      </div>
    </div>
  )
}


// ── Main App ───────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showContext, setShowContext] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [stocks, setStocks] = useState<Stock[]>([])

  useEffect(() => {
    fetch(`${API_BASE}/stocks`)
      .then(r => r.json())
      .then(setStocks)
      .catch(() => {})
  }, [])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [input])

  const sendMessage = async (text: string) => {
    const q = text.trim()
    if (!q || loading) return

    // Capture history before adding new messages
    const history = messages
      .filter(m => !m.streaming)
      .map(m => ({ role: m.role, content: m.content }))

    setInput('')
    // Add user message + an empty streaming assistant placeholder
    setMessages(prev => [
      ...prev,
      { role: 'user', content: q },
      { role: 'assistant', content: '', streaming: true },
    ])
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, chat_history: history }),
      })

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `Error ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // Helper: mutate the last (assistant) message in state
      const updateLast = (patch: Partial<Message>) =>
        setMessages(prev => {
          const msgs = [...prev]
          msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ...patch }
          return msgs
        })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE lines are separated by "\n\n"; each line starts with "data: "
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''   // last (possibly incomplete) chunk stays buffered

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6)

          let event: { type: string; content?: string; docs?: ContextDoc[]; extracted_years?: number[]; message?: string }
          try { event = JSON.parse(raw) } catch { continue }

          if (event.type === 'context') {
            updateLast({
              context: event.docs,
              extractedYears: event.extracted_years,
            })
          } else if (event.type === 'chunk') {
            setMessages(prev => {
              const msgs = [...prev]
              const last = msgs[msgs.length - 1]
              msgs[msgs.length - 1] = {
                ...last,
                content: last.content + (event.content ?? ''),
              }
              return msgs
            })
          } else if (event.type === 'done') {
            updateLast({ streaming: false })
          } else if (event.type === 'error') {
            updateLast({ content: event.message ?? 'Unknown error', streaming: false, error: true })
          }
        }
      }

      // Ensure streaming flag is cleared even if "done" event was missed
      updateLast({ streaming: false })
    } catch (err) {
      setMessages(prev => {
        const msgs = [...prev]
        msgs[msgs.length - 1] = {
          role: 'assistant',
          content: `Failed to get a response: ${(err as Error).message}`,
          streaming: false,
          error: true,
        }
        return msgs
      })
    } finally {
      setLoading(false)
      setTimeout(() => textareaRef.current?.focus(), 0)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="shell">
      {/* ── Sidebar ── */}
      {sidebarOpen && (
        <div className="overlay" onClick={() => setSidebarOpen(false)} />
      )}
      <aside className={`sidebar${sidebarOpen ? ' sidebar--open' : ''}`}>
        <div className="sidebar-top">
          <div className="sidebar-brand">
            <div className="brand-icon">FS</div>
            <span className="brand-name">FinSage</span>
          </div>
          <button
            className="new-chat-btn"
            onClick={() => { setMessages([]); setSidebarOpen(false) }}
          >
            + New chat
          </button>
        </div>

        {stocks.length > 0 && (
          <div className="sidebar-section">
            <p className="sidebar-section-label">Available Stocks</p>
            <div className="stock-list">
              {stocks.map(s => (
                <button
                  key={s.ticker}
                  className="stock-item "
                  onClick={() => {
                    setInput(`Analisis laporan keuangan ${s.ticker}`)
                    setSidebarOpen(false)
                    setTimeout(() => textareaRef.current?.focus(), 0)
                  }}
                >
                  <span className="stock-ticker">{s.ticker}</span>
                  <span className="stock-name">{s.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="sidebar-section">
          <p className="sidebar-section-label">Settings</p>
          <label className="toggle-row">
            <span>Show sources</span>
            <button
              role="switch"
              aria-checked={showContext}
              className={`toggle${showContext ? ' toggle--on' : ''}`}
              onClick={() => setShowContext(v => !v)}
            />
          </label>
        </div>

        <div className="sidebar-bottom">
          <p className="sidebar-stat">
            {messages.filter(m => m.role === 'user').length} message
            {messages.filter(m => m.role === 'user').length !== 1 ? 's' : ''} this session
          </p>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="main">
        {/* Top bar */}
        <header className="topbar">
          <button
            className="topbar-menu"
            onClick={() => setSidebarOpen(o => !o)}
            aria-label="Menu"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M3 12h18M3 6h18M3 18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
          <div className="topbar-brand">
            <div className="brand-icon brand-icon--sm">FS</div>
            <span>FinSage</span>
          </div>
          {!isEmpty && (
            <button
              className="topbar-new"
              onClick={() => setMessages([])}
              title="New chat"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          )}
        </header>

        {/* Message area */}
        <div className="chat-area">
          {isEmpty ? (
            /* ── Empty / welcome state ── */
            <div className="welcome">
              <div className="welcome-logo">
                <div className="brand-icon brand-icon--lg">FS</div>
              </div>
              <h1 className="welcome-title">FinSage</h1>
              <p className="welcome-sub">
                Ask anything about Indonesian public company financials.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s.label}
                    className="suggestion-card"
                    onClick={() => sendMessage(s.text)}
                  >
                    <span className="suggestion-icon">{s.icon}</span>
                    <span className="suggestion-label">{s.label}</span>
                    <span className="suggestion-arrow">→</span>
                  </button>
                ))}
              </div>

              {stocks.length > 0 && (
                <div className="welcome-stocks">
                  <p className="welcome-stocks-label">Available stocks</p>
                  <div className="welcome-stock-list">
                    {stocks.map(s => (
                      <button
                        key={s.ticker}
                        className="welcome-stock-chip"
                        onClick={() => {
                          setInput(`Analisis laporan keuangan ${s.ticker}`)
                          setTimeout(() => textareaRef.current?.focus(), 0)
                        }}
                      >
                        <span className="welcome-stock-chip-ticker">{s.ticker}</span>
                        <span className="welcome-stock-chip-name">{s.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ── Messages ── */
            <div className="messages">
              {messages.map((msg, i) => (
                <MessageBubble key={i} msg={msg} showContext={showContext} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* ── Fixed bottom input ── */}
        <div className="input-bar">
          <div className="input-wrap">
            <textarea
              ref={textareaRef}
              className="input-field"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about financials, risk metrics, earnings…"
              rows={1}
              disabled={loading}
            />
            <button
              className={`send-btn${input.trim() && !loading ? ' send-btn--active' : ''}`}
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || loading}
              aria-label="Send"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
          <p className="input-hint">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}
