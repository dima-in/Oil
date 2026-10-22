import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useDataRefresh } from '../lib/events'
import { addDaysIso, dateRu, relativeDay, todayIso } from '../lib/format'
import PageHeader from './PageHeader'

const FILTERS = [
  { id: 'open', label: 'Открытые' },
  { id: 'done', label: 'Выполненные' },
  { id: 'all', label: 'Все' },
]
const PRIORITIES = [
  { value: 0, label: 'Низкий' },
  { value: 1, label: 'Обычный' },
  { value: 2, label: 'Важный' },
]

export default function TasksView() {
  const [filter, setFilter] = useState('open')
  const [tasks, setTasks] = useState(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ title: '', due_date: todayIso(), priority: 1, details: '' })

  const load = useCallback(async () => {
    try {
      const rows = await api.crm.tasks({ status: filter })
      setError('')
      setTasks(rows)
    } catch (err) {
      setError(err.message)
    }
  }, [filter])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии экрана
    load()
  }, [load])
  useDataRefresh(load)

  const create = async (event) => {
    event.preventDefault()
    if (!form.title.trim()) return
    try {
      await api.crm.createTask({ ...form, priority: Number(form.priority) })
      setForm({ title: '', due_date: todayIso(), priority: 1, details: '' })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const toggle = async (task) => {
    try {
      await api.crm.updateTask(task.id, { is_done: !task.is_done })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const postpone = async (task) => {
    try {
      await api.crm.updateTask(task.id, { due_date: addDaysIso(todayIso(), 1) })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const remove = async (task) => {
    if (!window.confirm(`Удалить задачу «${task.title}»?`)) return
    try {
      await api.crm.deleteTask(task.id)
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="CRM"
        title="Задачи"
        description="Напоминания и дела: перезвонить, отжать, закупить. Задачи по клиенту видны и в его карточке."
      />

      <section className="section-card">
        <form className="task-form" onSubmit={create}>
          <input
            className="ios-input task-form__title"
            placeholder="Новая задача…"
            value={form.title}
            onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
          />
          <input
            className="ios-input"
            type="date"
            value={form.due_date}
            onChange={(event) => setForm((prev) => ({ ...prev, due_date: event.target.value }))}
          />
          <select
            className="ios-input"
            value={form.priority}
            onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
          >
            {PRIORITIES.map((priority) => (
              <option key={priority.value} value={priority.value}>
                {priority.label}
              </option>
            ))}
          </select>
          <button type="submit" className="ios-button primary">
            Добавить
          </button>
        </form>
      </section>

      <div className="filter-row filter-row--start">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={filter === item.id ? 'filter-chip filter-chip--active' : 'filter-chip'}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error ? <div className="notice notice--error">{error}</div> : null}

      {tasks === null ? (
        <div className="state-panel">Загрузка…</div>
      ) : tasks.length === 0 ? (
        <div className="state-panel">Задач нет.</div>
      ) : (
        <section className="section-card crm-block">
          <div className="crm-list">
            {tasks.map((task) => (
              <div key={task.id} className={task.is_done ? 'task-row task-row--done' : 'task-row'}>
                <input type="checkbox" checked={task.is_done} onChange={() => toggle(task)} aria-label="Готово" />
                <span className="task-row__body">
                  <span className="task-row__title">
                    {task.priority === 2 ? <span className="tag tag--danger">важно</span> : null} {task.title}
                  </span>
                  <span className={task.is_overdue ? 'task-row__due task-row__due--overdue' : 'task-row__due'}>
                    {task.due_date ? `${dateRu(task.due_date)} · ${relativeDay(task.due_date)}` : 'без срока'}
                    {task.customer_id ? (
                      <>
                        {' · '}
                        <Link to={`/customers/${task.customer_id}`} className="crm-link">
                          {`${task.customer_name || ''} ${task.customer_surname || ''}`.trim() || 'клиент'}
                        </Link>
                      </>
                    ) : null}
                    {task.order_id ? (
                      <>
                        {' · '}
                        <Link to={`/orders?focus=${task.order_id}`} className="crm-link">
                          заказ №{task.order_id}
                        </Link>
                      </>
                    ) : null}
                  </span>
                  {task.details ? <span className="task-row__details">{task.details}</span> : null}
                </span>
                <span className="task-row__actions">
                  {!task.is_done ? (
                    <button type="button" className="link-button" onClick={() => postpone(task)}>
                      На завтра
                    </button>
                  ) : null}
                  <button type="button" className="link-danger" onClick={() => remove(task)}>
                    Удалить
                  </button>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
