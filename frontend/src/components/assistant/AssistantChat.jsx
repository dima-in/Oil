import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { getStoredUser } from '../../lib/auth'
import { notifyDataChanged } from '../../lib/events'
import { useDictation } from '../../lib/speech'
import Icon from '../Icon'
import { ORDER_TEMPLATE } from '../../lib/constants'
import { useAssistant } from './AssistantContext'
import RichText from './RichText'

const HISTORY_LIMIT = 40

const QUICK_PROMPTS = [
  { label: 'Что сегодня важно?', text: 'Что сегодня важно сделать в первую очередь?' },
  { label: 'Разобрать заявку', template: ORDER_TEMPLATE },
  { label: 'Выручка за месяц', text: 'Какая выручка и прибыль в этом месяце? Сравни с прошлым.' },
  { label: 'План прессов', text: 'Распиши загрузку прессов на неделю под открытые заказы.' },
  { label: 'Кто давно не заказывал', text: 'Кто из постоянных клиентов давно не заказывал? Кому стоит написать?' },
  { label: 'Записать расход', template: 'Запиши расход: ' },
]

const ACTION_STATUS = {
  pending: 'ждёт подтверждения',
  running: 'выполняется',
  done: 'выполнено',
  failed: 'не выполнено',
  cancelled: 'отменено',
  expired: 'устарело',
}

function storageKey() {
  return `oilpress-chat-${getStoredUser()?.username || 'anon'}`
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(storageKey()) || '[]')
  } catch {
    return []
  }
}

function saveHistory(messages) {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(messages.slice(-HISTORY_LIMIT)))
  } catch {
    /* private mode: история живёт до перезагрузки */
  }
}

// Модели нужно знать, чем закончились черновики прошлых ходов, иначе она предложит их снова.
function toApiMessage(message) {
  let content = message.content || ''
  if (message.actions?.length) {
    const notes = message.actions.map((action) => {
      const result = action.result?.message ? `: ${action.result.message}` : ''
      return `${action.title} — ${ACTION_STATUS[action.status] || action.status}${result}`
    })
    content += `\n\n[Черновики: ${notes.join('; ')}]`
  }
  return { role: message.role, content }
}

function contextFromPath(pathname) {
  const customer = pathname.match(/^\/customers\/(\d+)/)
  if (customer) return { customer_id: Number(customer[1]), page: 'карточка клиента' }
  const pages = {
    '/': 'сводка «Сегодня»',
    '/orders': 'заказы',
    '/customers': 'клиенты',
    '/tasks': 'задачи',
    '/production': 'остатки и отжим',
  }
  return pages[pathname] ? { page: pages[pathname] } : null
}

function ActionCard({ action, onUpdate }) {
  const [busy, setBusy] = useState(false)

  const run = async (kind) => {
    setBusy(true)
    try {
      const updated = kind === 'confirm' ? await api.assistant.confirm(action.id) : await api.assistant.cancel(action.id)
      onUpdate(updated)
      if (updated.status === 'done') notifyDataChanged()
    } catch (error) {
      onUpdate({ ...action, status: 'failed', result: { message: error.message } })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`action-card action-card--${action.status}`}>
      <div className="action-card__head">
        <span className="action-card__title">{action.title}</span>
        <span className="action-card__status">{ACTION_STATUS[action.status] || action.status}</span>
      </div>
      <div className="action-card__summary">{action.summary}</div>
      {action.result?.message && action.status !== 'pending' ? (
        <div className="action-card__result">
          {action.result.message}
          {action.result.link ? (
            <>
              {' · '}
              <Link to={action.result.link} className="crm-link">
                открыть
              </Link>
            </>
          ) : null}
        </div>
      ) : null}
      {action.status === 'pending' ? (
        <div className="action-card__buttons">
          <button type="button" className="ios-button success" disabled={busy} onClick={() => run('confirm')}>
            {busy ? 'Выполняю…' : 'Подтвердить'}
          </button>
          <button type="button" className="ios-button secondary" disabled={busy} onClick={() => run('cancel')}>
            Отмена
          </button>
        </div>
      ) : null}
    </div>
  )
}

function DataTables({ tables }) {
  if (!tables?.length) return null
  return tables.map((table, index) => (
    <details key={index} className="chat-details">
      <summary>
        Данные из базы: {table.rows.length} строк{table.truncated ? ' (показаны первые)' : ''}
      </summary>
      <code className="chat-sql">{table.query}</code>
      <div className="table-wrap">
        <table className="price-table price-table--compact">
          <thead>
            <tr>
              {table.columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((value, cellIndex) => (
                  <td key={cellIndex}>{value === null ? '—' : String(value)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  ))
}

function Trace({ trace }) {
  if (!trace?.length) return null
  return (
    <details className="chat-details chat-details--trace">
      <summary>Как искал: {trace.map((step) => step.title).join(' → ')}</summary>
      <ol className="chat-trace">
        {trace.map((step, index) => (
          <li key={index} className={step.ok ? '' : 'chat-trace__error'}>
            <strong>{step.title}</strong> — {step.preview}
          </li>
        ))}
      </ol>
    </details>
  )
}

export default function AssistantChat({ variant = 'drawer' }) {
  const [messages, setMessages] = useState(loadHistory)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null)
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const location = useLocation()
  const navigate = useNavigate()
  const assistant = useAssistant()
  const pageContext = useMemo(() => contextFromPath(location.pathname), [location.pathname])
  const dictationBase = useRef('')
  const dictation = useDictation((finalText, interim) => {
    const base = dictationBase.current
    const glue = base && !/[\s\n]$/.test(base) ? ' ' : ''
    setInput(`${base}${glue}${[finalText, interim].filter(Boolean).join(' ')}`)
  })

  const toggleDictation = () => {
    if (dictation.listening) {
      dictation.stop()
    } else {
      dictationBase.current = input
      dictation.start()
    }
  }

  useEffect(() => {
    api.assistant.status().then(setStatus).catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    saveHistory(messages)
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const send = useCallback(
    async (text, context) => {
      const question = String(text || '').trim()
      if (!question || loading) return
      const userMessage = { id: `u${Date.now()}`, role: 'user', content: question }
      const history = [...messages.filter((message) => !message.error), userMessage]
      setMessages((prev) => [...prev, userMessage])
      setInput('')
      setLoading(true)
      try {
        const response = await api.assistant.chat(history.slice(-24).map(toApiMessage), context || pageContext)
        setMessages((prev) => [
          ...prev,
          {
            id: `a${Date.now()}`,
            role: 'assistant',
            content: response.reply,
            actions: response.actions,
            trace: response.trace,
            tables: response.tables,
          },
        ])
      } catch (error) {
        setMessages((prev) => [...prev, { id: `e${Date.now()}`, role: 'assistant', content: error.message, error: true }])
      } finally {
        setLoading(false)
        inputRef.current?.focus()
      }
    },
    [loading, messages, pageContext],
  )

  // Вопрос, заданный кнопкой с другого экрана («Сводка от ИИ», подсказки на «Сегодня»).
  useEffect(() => {
    if (assistant.request && !loading) {
      const { text, context, prefill, listen } = assistant.request
      assistant.consumeRequest()
      if (prefill) {
        setInput(text)
        requestAnimationFrame(() => inputRef.current?.focus())
        if (listen && dictation.supported) {
          dictationBase.current = text
          dictation.start()
        }
      } else {
        send(text, context)
      }
    }
  }, [assistant, dictation, loading, send])

  const updateAction = (messageId, updated) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId
          ? { ...message, actions: message.actions.map((action) => (action.id === updated.id ? updated : action)) }
          : message,
      ),
    )
  }

  const applyPrompt = (prompt) => {
    if (prompt.template) {
      setInput(prompt.template)
      requestAnimationFrame(() => inputRef.current?.focus())
    } else {
      send(prompt.text)
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      dictation.stop()
      send(input)
    }
  }

  return (
    <div className={`assistant assistant--${variant}`}>
      <div className="assistant__head">
        <div>
          <div className="assistant__title">
            <Icon name="spark" /> ИИ-помощник
          </div>
          <div className="assistant__subtitle">
            {pageContext?.page ? `Контекст: ${pageContext.page}` : 'Видит всю базу, изменения — только после подтверждения'}
          </div>
        </div>
        <div className="assistant__head-actions">
          {messages.length ? (
            <button type="button" className="icon-button" title="Очистить диалог" onClick={() => setMessages([])}>
              <Icon name="trash" />
            </button>
          ) : null}
          {variant === 'drawer' ? (
            <>
              <button
                type="button"
                className="icon-button"
                title="Открыть на весь экран"
                onClick={() => {
                  assistant.close()
                  navigate('/assistant')
                }}
              >
                <Icon name="expand" />
              </button>
              <button type="button" className="icon-button" title="Закрыть" onClick={assistant.close}>
                <Icon name="close" />
              </button>
            </>
          ) : null}
        </div>
      </div>

      {status && !status.enabled ? (
        <div className="notice notice--error assistant__notice">
          ИИ выключен: на сервере не задан OPENROUTER_API_KEY.
        </div>
      ) : null}

      <div className="assistant__messages" ref={listRef}>
        {messages.length === 0 ? (
          <div className="assistant__empty">
            <p>
              Спросите о бизнесе, вставьте заявку клиента из Avito/WhatsApp или попросите записать расход —
              помощник найдёт данные и подготовит действие, а вы подтвердите его кнопкой.
            </p>
            <div className="prompt-list">
              {QUICK_PROMPTS.map((prompt) => (
                <button key={prompt.label} type="button" className="prompt-chip" onClick={() => applyPrompt(prompt)}>
                  {prompt.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`chat-bubble chat-bubble--${message.role}${message.error ? ' chat-bubble--error' : ''}`}
            >
              {message.role === 'assistant' && !message.error ? (
                <RichText text={message.content} />
              ) : (
                <div className="chat-bubble__plain">{message.content}</div>
              )}
              {message.actions?.map((action) => (
                <ActionCard key={action.id} action={action} onUpdate={(updated) => updateAction(message.id, updated)} />
              ))}
              <DataTables tables={message.tables} />
              <Trace trace={message.trace} />
            </div>
          ))
        )}
        {loading ? (
          <div className="chat-bubble chat-bubble--assistant chat-bubble--loading">
            <span className="typing-dots">
              <i />
              <i />
              <i />
            </span>
            Смотрю базу…
          </div>
        ) : null}
      </div>

      {messages.length ? (
        <div className="prompt-list prompt-list--inline">
          {QUICK_PROMPTS.slice(0, 4).map((prompt) => (
            <button key={prompt.label} type="button" className="prompt-chip prompt-chip--small" onClick={() => applyPrompt(prompt)}>
              {prompt.label}
            </button>
          ))}
        </div>
      ) : null}

      {dictation.error ? <div className="assistant__hint assistant__hint--error">{dictation.error}</div> : null}
      {dictation.listening ? (
        <div className="assistant__hint assistant__hint--live">
          <span className="rec-dot" /> Слушаю… говорите заказ: кто, что, сколько, когда. Нажмите микрофон ещё раз, чтобы закончить.
        </div>
      ) : null}

      <form
        className="assistant__composer"
        onSubmit={(event) => {
          event.preventDefault()
          dictation.stop()
          send(input)
        }}
      >
        <textarea
          ref={inputRef}
          className="ios-input assistant__input"
          rows={input.includes('\n') ? 4 : 2}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Вопрос или заявка — текстом или голосом"
          disabled={loading}
        />
        <div className="assistant__composer-buttons">
          <button
            type="button"
            className={`icon-button icon-button--mic${dictation.listening ? ' icon-button--recording' : ''}`}
            title={dictation.supported ? 'Надиктовать' : dictation.reason}
            onClick={toggleDictation}
            disabled={loading}
          >
            <Icon name="mic" />
          </button>
          <button type="submit" className="ios-button primary assistant__send" disabled={loading || !input.trim()}>
            <Icon name="send" />
          </button>
        </div>
      </form>
    </div>
  )
}
