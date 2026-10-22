import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useDataRefresh } from '../lib/events'
import { dateRu, dateTimeRu, money, phoneHref } from '../lib/format'
import { useAssistant } from './assistant/AssistantContext'
import { CustomerForm } from './CustomersView'
import OrderRow from './OrderRow'
import PageHeader from './PageHeader'

const KINDS = [
  { value: 'note', label: 'Заметка' },
  { value: 'call', label: 'Звонок' },
  { value: 'message', label: 'Сообщение' },
  { value: 'meeting', label: 'Встреча' },
]

export default function CustomerCard() {
  const { id } = useParams()
  const [customer, setCustomer] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [note, setNote] = useState({ kind: 'note', text: '' })
  const [task, setTask] = useState({ title: '', due_date: '' })
  const assistant = useAssistant()

  const load = useCallback(async () => {
    try {
      const fresh = await api.crm.customer(id)
      setError('')
      setCustomer(fresh)
    } catch (err) {
      setError(err.message)
    }
  }, [id])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии экрана
    load()
  }, [load])
  useDataRefresh(load)

  const addNote = async (event) => {
    event.preventDefault()
    if (!note.text.trim()) return
    try {
      await api.crm.addInteraction(id, note)
      setNote({ kind: note.kind, text: '' })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const addTask = async (event) => {
    event.preventDefault()
    if (!task.title.trim()) return
    try {
      await api.crm.createTask({ ...task, customer_id: Number(id) })
      setTask({ title: '', due_date: '' })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const toggleTask = async (item) => {
    try {
      await api.crm.updateTask(item.id, { is_done: !item.is_done })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  if (error) return <div className="notice notice--error">{error}</div>
  if (!customer) return <div className="state-panel">Загрузка карточки…</div>

  const context = { customer_id: customer.id, page: 'карточка клиента' }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={
          <Link to="/customers" className="crm-link">
            ← Клиенты
          </Link>
        }
        title={customer.full_name || 'Без имени'}
        description={[customer.phone, customer.address, customer.email].filter(Boolean).join(' · ') || 'Контакты не заполнены'}
        actions={
          <div className="header-actions">
            {customer.phone ? (
              <a className="ios-button secondary" href={phoneHref(customer.phone)}>
                Позвонить
              </a>
            ) : null}
            <button type="button" className="ios-button secondary" onClick={() => setEditing((value) => !value)}>
              {editing ? 'Закрыть' : 'Изменить'}
            </button>
            <button
              type="button"
              className="ios-button primary"
              onClick={() =>
                assistant.ask(
                  'Дай короткую сводку по этому клиенту: что заказывает, как часто, есть ли открытые вопросы, и что ему предложить.',
                  context,
                )
              }
            >
              Сводка от ИИ
            </button>
          </div>
        }
      />

      {editing ? (
        <section className="section-card">
          <CustomerForm
            initial={customer}
            onSubmit={async (form) => {
              await api.crm.updateCustomer(customer.id, form)
              setEditing(false)
              load()
            }}
            onCancel={() => setEditing(false)}
          />
        </section>
      ) : null}

      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi__label">Заказов</div>
          <div className="kpi__value">{customer.orders_count}</div>
          <div className="kpi__hint">открытых: {customer.open_orders}</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Сумма покупок</div>
          <div className="kpi__value">{money(customer.total_spent)}</div>
          <div className="kpi__hint">
            средний чек {money(customer.orders_count ? customer.total_spent / customer.orders_count : 0)}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Последний заказ</div>
          <div className="kpi__value kpi__value--small">{dateRu(customer.last_order_date)}</div>
          <div className="kpi__hint">клиент с {dateRu(customer.created_at)}</div>
        </div>
        <div className="kpi">
          <div className="kpi__label">Любимое</div>
          <div className="tag-list">
            {customer.favourite_products.length
              ? customer.favourite_products.map((item) => (
                  <span key={item.oil_name} className="tag">
                    {item.oil_name} ×{item.count}
                  </span>
                ))
              : <span className="muted">пока нет</span>}
          </div>
        </div>
      </div>

      {customer.source || customer.tags_list.length || customer.note ? (
        <section className="section-card crm-block">
          <div className="tag-list">
            {customer.source ? <span className="tag tag--source">{customer.source}</span> : null}
            {customer.tags_list.map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
          {customer.note ? <p className="crm-note">{customer.note}</p> : null}
        </section>
      ) : null}

      <div className="dashboard-grid">
        <section className="section-card crm-block crm-block--span">
          <div className="crm-block__head">
            <h2 className="crm-block__title">
              Заказы <span className="count-pill">{customer.orders.length}</span>
            </h2>
            <Link to="/quick-order" className="crm-link">
              Новый заказ
            </Link>
          </div>
          {customer.orders.length ? (
            <div className="crm-list">
              {customer.orders.map((order) => (
                <OrderRow key={order.id} order={order} onChanged={load} showCustomer={false} />
              ))}
            </div>
          ) : (
            <div className="crm-empty">Заказов ещё не было.</div>
          )}
        </section>

        <section className="section-card crm-block">
          <div className="crm-block__head">
            <h2 className="crm-block__title">История общения</h2>
          </div>
          <form className="inline-form" onSubmit={addNote}>
            <select
              className="ios-input inline-form__kind"
              value={note.kind}
              onChange={(event) => setNote((prev) => ({ ...prev, kind: event.target.value }))}
            >
              {KINDS.map((kind) => (
                <option key={kind.value} value={kind.value}>
                  {kind.label}
                </option>
              ))}
            </select>
            <input
              className="ios-input"
              placeholder="О чём договорились…"
              value={note.text}
              onChange={(event) => setNote((prev) => ({ ...prev, text: event.target.value }))}
            />
            <button type="submit" className="ios-button primary">
              Добавить
            </button>
          </form>
          {customer.interactions.length ? (
            <ul className="timeline">
              {customer.interactions.map((item) => (
                <li key={item.id} className="timeline__item">
                  <div className="timeline__meta">
                    <span className="tag">{item.kind_label}</span> {dateTimeRu(item.created_at)}
                    {item.author ? ` · ${item.author}` : ''}
                  </div>
                  <div className="timeline__text">{item.text}</div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="crm-empty">Записей пока нет.</div>
          )}
        </section>

        <section className="section-card crm-block">
          <div className="crm-block__head">
            <h2 className="crm-block__title">Задачи по клиенту</h2>
          </div>
          <form className="inline-form" onSubmit={addTask}>
            <input
              className="ios-input"
              placeholder="Что сделать…"
              value={task.title}
              onChange={(event) => setTask((prev) => ({ ...prev, title: event.target.value }))}
            />
            <input
              className="ios-input inline-form__date"
              type="date"
              value={task.due_date}
              onChange={(event) => setTask((prev) => ({ ...prev, due_date: event.target.value }))}
            />
            <button type="submit" className="ios-button primary">
              Добавить
            </button>
          </form>
          {customer.tasks.length ? (
            <div className="crm-list">
              {customer.tasks.map((item) => (
                <label key={item.id} className={item.is_done ? 'task-row task-row--done' : 'task-row'}>
                  <input type="checkbox" checked={item.is_done} onChange={() => toggleTask(item)} />
                  <span className="task-row__body">
                    <span className="task-row__title">{item.title}</span>
                    <span className={item.is_overdue ? 'task-row__due task-row__due--overdue' : 'task-row__due'}>
                      {item.due_date ? dateRu(item.due_date) : 'без срока'}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <div className="crm-empty">Задач нет.</div>
          )}
        </section>
      </div>
    </div>
  )
}
