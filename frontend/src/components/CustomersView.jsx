import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { dateRu, money } from '../lib/format'
import PageHeader from './PageHeader'

const EMPTY_FORM = { name: '', surname: '', phone: '', address: '', email: '', source: '', tags: '', note: '' }
const SOURCES = ['Avito', 'Ozon', 'сарафан', 'соцсети', 'сайт', 'опт']

export function CustomerForm({ initial = EMPTY_FORM, onSubmit, onCancel, submitLabel = 'Сохранить' }) {
  const [form, setForm] = useState({ ...EMPTY_FORM, ...initial })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const set = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSubmit(form)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form-grid" onSubmit={handleSubmit}>
      <input className="ios-input" placeholder="Имя *" value={form.name} onChange={set('name')} required />
      <input className="ios-input" placeholder="Фамилия" value={form.surname || ''} onChange={set('surname')} />
      <input className="ios-input" placeholder="Телефон" value={form.phone || ''} onChange={set('phone')} />
      <input className="ios-input" placeholder="E-mail" value={form.email || ''} onChange={set('email')} />
      <input
        className="ios-input form-grid__wide"
        placeholder="Адрес"
        value={form.address || ''}
        onChange={set('address')}
      />
      <input
        className="ios-input"
        placeholder="Источник"
        list="customer-sources"
        value={form.source || ''}
        onChange={set('source')}
      />
      <datalist id="customer-sources">
        {SOURCES.map((source) => (
          <option key={source} value={source} />
        ))}
      </datalist>
      <input className="ios-input" placeholder="Теги через запятую" value={form.tags || ''} onChange={set('tags')} />
      <textarea
        className="ios-input form-grid__wide"
        rows={2}
        placeholder="Заметка"
        value={form.note || ''}
        onChange={set('note')}
      />
      {error ? <div className="notice notice--error form-grid__wide">{error}</div> : null}
      <div className="form-grid__actions form-grid__wide">
        {onCancel ? (
          <button type="button" className="ios-button secondary" onClick={onCancel}>
            Отмена
          </button>
        ) : null}
        <button type="submit" className="ios-button primary" disabled={saving}>
          {saving ? 'Сохраняю…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function CustomersView() {
  const [query, setQuery] = useState('')
  const [customers, setCustomers] = useState(null)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    // Поиск с небольшой задержкой, чтобы не дёргать базу на каждую букву.
    const timer = setTimeout(async () => {
      try {
        setError('')
        setCustomers(await api.crm.customers(query.trim()))
      } catch (err) {
        setError(err.message)
      }
    }, 250)
    return () => clearTimeout(timer)
  }, [query])

  const handleCreate = async (form) => {
    const created = await api.crm.createCustomer(form)
    navigate(`/customers/${created.id}`)
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="CRM"
        title="Клиенты"
        description="Карточки с историей заказов, заметками и задачами. Ищите по имени, телефону, тегу или адресу."
        actions={
          <button type="button" className="ios-button primary" onClick={() => setCreating((value) => !value)}>
            {creating ? 'Скрыть форму' : 'Новый клиент'}
          </button>
        }
      />

      {creating ? (
        <section className="section-card">
          <CustomerForm onSubmit={handleCreate} onCancel={() => setCreating(false)} submitLabel="Добавить клиента" />
        </section>
      ) : null}

      <input
        className="ios-input search-input"
        placeholder="Поиск: имя, телефон, тег…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />

      {error ? <div className="notice notice--error">{error}</div> : null}

      {customers === null ? (
        <div className="state-panel">Загрузка…</div>
      ) : customers.length === 0 ? (
        <div className="state-panel">{query ? 'Никого не нашлось.' : 'Клиентов пока нет.'}</div>
      ) : (
        <section className="section-card section-card--flush">
          <div className="table-wrap">
            <table className="price-table crm-table">
              <thead>
                <tr>
                  <th>Клиент</th>
                  <th>Телефон</th>
                  <th>Источник / теги</th>
                  <th className="num">Заказов</th>
                  <th className="num">Сумма</th>
                  <th>Последний заказ</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td>
                      <Link to={`/customers/${customer.id}`} className="crm-link">
                        {customer.full_name || 'без имени'}
                      </Link>
                      {customer.open_orders ? (
                        <span className="count-pill count-pill--accent">{customer.open_orders} откр.</span>
                      ) : null}
                    </td>
                    <td className="nowrap">{customer.phone || '—'}</td>
                    <td>
                      <div className="tag-list">
                        {customer.source ? <span className="tag tag--source">{customer.source}</span> : null}
                        {customer.tags_list.map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="num">{customer.orders_count}</td>
                    <td className="num nowrap">{money(customer.total_spent)}</td>
                    <td className="nowrap">{dateRu(customer.last_order_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
