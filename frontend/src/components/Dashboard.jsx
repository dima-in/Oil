import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useDataRefresh } from '../lib/events'
import { dateRu, money, volume } from '../lib/format'
import { useAssistant } from './assistant/AssistantContext'
import OrderRow from './OrderRow'
import PageHeader from './PageHeader'

const AI_PROMPTS = [
  'Что сегодня важно сделать в первую очередь?',
  'Кому из клиентов пора напомнить об оплате или заказе?',
  'Что и сколько нужно отжать на этой неделе?',
  'Сравни выручку этого месяца с прошлым',
]

function Kpi({ label, value, hint, tone }) {
  return (
    <div className={`kpi${tone ? ` kpi--${tone}` : ''}`}>
      <div className="kpi__label">{label}</div>
      <div className="kpi__value">{value}</div>
      {hint ? <div className="kpi__hint">{hint}</div> : null}
    </div>
  )
}

function OrdersBlock({ title, orders, empty, tone, onChanged }) {
  return (
    <section className="section-card crm-block">
      <div className="crm-block__head">
        <h2 className="crm-block__title">
          {title}
          <span className={`count-pill${tone ? ` count-pill--${tone}` : ''}`}>{orders.length}</span>
        </h2>
      </div>
      {orders.length ? (
        <div className="crm-list">
          {orders.map((order) => (
            <OrderRow key={order.id} order={order} onChanged={onChanged} />
          ))}
        </div>
      ) : (
        <div className="crm-empty">{empty}</div>
      )}
    </section>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const assistant = useAssistant()

  const load = useCallback(async () => {
    try {
      const fresh = await api.crm.dashboard()
      setError('')
      setData(fresh)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии экрана
    load()
  }, [load])
  useDataRefresh(load)

  const completeTask = async (task) => {
    try {
      await api.crm.updateTask(task.id, { is_done: true })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  if (error) return <div className="notice notice--error">{error}</div>
  if (!data) return <div className="state-panel">Собираю сводку…</div>

  const { month } = data
  const needs = data.production_needs.filter((item) => item.shortage_ml > 0)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={dateRu(data.today)}
        title="Сегодня"
        description="Что отгрузить, кому напомнить и что отжать — по данным базы."
        actions={
          <div className="header-actions">
            <Link to="/quick-order" className="ios-button secondary">
              Записать заказ
            </Link>
            <button type="button" className="ios-button primary" onClick={() => assistant.open()}>
              Спросить ИИ
            </button>
          </div>
        }
      />

      <div className="kpi-grid">
        <Kpi label="Выручка за месяц" value={money(month.revenue)} hint={`${month.orders_count} заказов`} />
        <Kpi
          label="Чистая прибыль"
          value={money(month.net_profit)}
          hint={`валовая ${money(month.gross_profit)} − расходы ${money(month.expenses)}`}
          tone={month.net_profit < 0 ? 'danger' : 'success'}
        />
        <Kpi
          label="Открытые заказы"
          value={data.open_orders.count}
          hint={`на ${money(data.open_orders.sum)}`}
        />
        <Kpi
          label="Клиенты"
          value={data.customers_total}
          hint={month.customers_new ? `+${month.customers_new} в этом месяце` : 'новых в этом месяце нет'}
        />
        <Kpi
          label="Задачи"
          value={data.tasks_open_count}
          hint={data.tasks_due.length ? `${data.tasks_due.length} на сегодня` : 'на сегодня нет'}
          tone={data.tasks_due.some((task) => task.is_overdue) ? 'warning' : undefined}
        />
      </div>

      <section className="ai-strip">
        <div className="ai-strip__text">
          <strong>ИИ-помощник</strong> видит всю базу: ответит на вопрос, разберёт заявку клиента и подготовит
          заказ или задачу — вы только подтверждаете.
        </div>
        <div className="ai-strip__prompts">
          {AI_PROMPTS.map((prompt) => (
            <button key={prompt} type="button" className="prompt-chip" onClick={() => assistant.ask(prompt)}>
              {prompt}
            </button>
          ))}
        </div>
      </section>

      <div className="dashboard-grid">
        <OrdersBlock
          title="Отгрузить сегодня"
          orders={data.ship_today}
          empty="На сегодня отгрузок нет."
          tone="accent"
          onChanged={load}
        />
        <OrdersBlock
          title="Просрочено"
          orders={data.overdue}
          empty="Просроченных заказов нет."
          tone="danger"
          onChanged={load}
        />
        <OrdersBlock
          title="Ждут предоплаты"
          orders={data.awaiting_payment}
          empty="Никто не ждёт оплаты."
          tone="warning"
          onChanged={load}
        />
        <OrdersBlock
          title="Ближайшие 7 дней"
          orders={data.upcoming}
          empty="На неделю вперёд отгрузок нет."
          onChanged={load}
        />

        <section className="section-card crm-block">
          <div className="crm-block__head">
            <h2 className="crm-block__title">
              Задачи на сегодня
              <span className="count-pill">{data.tasks_due.length}</span>
            </h2>
            <Link to="/tasks" className="crm-link">
              Все задачи
            </Link>
          </div>
          {data.tasks_due.length ? (
            <div className="crm-list">
              {data.tasks_due.map((task) => (
                <label key={task.id} className="task-row">
                  <input type="checkbox" onChange={() => completeTask(task)} />
                  <span className="task-row__body">
                    <span className="task-row__title">{task.title}</span>
                    <span className={task.is_overdue ? 'task-row__due task-row__due--overdue' : 'task-row__due'}>
                      {task.due_date ? dateRu(task.due_date) : 'без срока'}
                      {task.customer_id ? ` · ${task.customer_name || ''} ${task.customer_surname || ''}` : ''}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <div className="crm-empty">Задач на сегодня нет.</div>
          )}
        </section>

        <section className="section-card crm-block">
          <div className="crm-block__head">
            <h2 className="crm-block__title">
              Что отжать (14 дней)
              <span className={`count-pill${needs.length ? ' count-pill--warning' : ''}`}>{needs.length}</span>
            </h2>
            <Link to="/production" className="crm-link">
              Остатки
            </Link>
          </div>
          {needs.length ? (
            <div className="table-wrap">
              <table className="price-table price-table--compact">
                <thead>
                  <tr>
                    <th>Масло</th>
                    <th>Не хватает</th>
                    <th>Закладок</th>
                    <th>К дате</th>
                  </tr>
                </thead>
                <tbody>
                  {needs.map((item) => (
                    <tr key={item.oil_name}>
                      <td>{item.oil_name}</td>
                      <td>{volume(item.shortage_ml)}</td>
                      <td>{item.profile_ready ? item.batches_needed : <span className="muted">нет нормы</span>}</td>
                      <td>{dateRu(item.earliest_shipping)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="crm-empty">Под ближайшие заказы масла хватает.</div>
          )}
        </section>
      </div>
    </div>
  )
}
