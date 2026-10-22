import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import PageHeader from './PageHeader'
import StatusSelect from './StatusSelect'
import { api } from '../lib/api'
import { useDataRefresh } from '../lib/events'
import { useStatuses } from '../lib/statuses'

function formatBottles(items) {
  return items
    .map((item) => `${item.count}×${item.volume} мл`)
    .join(', ')
}

function totalOrderProfit(items) {
  return items.reduce((sum, item) => sum + Number(item.profit || 0), 0)
}

function totalOrderSeedWeight(items) {
  return items.reduce(
    (sum, item) => sum + Number(item.seed_weight_kg || 0) * Number(item.count || 0),
    0,
  )
}

function ProductionPlan({ plan }) {
  if (!plan?.length) {
    return null
  }

  return (
    <section className="production-plan">
      <div className="production-plan__title">План производства</div>
      <div className="production-plan__list">
        {plan.map((item) => (
          <div key={item.oil_name} className="production-plan__card">
            <div className="production-plan__head">
              <strong>{item.oil_name}</strong>
              <span>{item.total_volume_ml.toLocaleString('ru-RU')} мл</span>
            </div>
            <div className="production-plan__meta">{formatBottles(item.bottles)}</div>

            {item.profile_ready ? (
              <>
                <div className="production-plan__meta">
                  Закладка: {item.batch_seed_weight_kg.toLocaleString('ru-RU', { maximumFractionDigits: 3 })} кг
                  , выход {item.yield_percent.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}%
                </div>
                <div className="production-plan__meta">
                  С одной закладки: {Math.round(item.output_per_batch_ml || 0).toLocaleString('ru-RU')} мл
                </div>
                <div className="production-plan__result">
                  Нужно закладок: {item.batches_needed}
                </div>
                <div className="production-plan__meta">
                  Даты: {item.suggested_dates.length ? item.suggested_dates.join(', ') : 'не рассчитаны'}
                </div>
              </>
            ) : (
              <div className="production-plan__warning">
                Нет производственного профиля для этого масла
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export default function OrdersView() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('open')
  const [search, setSearch] = useState('')
  const [searchParams] = useSearchParams()
  const focusId = Number(searchParams.get('focus')) || null
  const statuses = useStatuses()

  const loadOrders = useCallback(async () => {
    try {
      const data = await api.getOrders()
      setOrders(data)
    } catch (error) {
      console.error('Error fetching orders:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOrders()
  }, [loadOrders])
  useDataRefresh(loadOrders)

  // Переход «открыть заказ №N» из помощника или сводки: показываем его, даже если фильтр другой.
  useEffect(() => {
    if (!focusId || loading) return
    setFilter('all')
    requestAnimationFrame(() =>
      document.getElementById(`order-${focusId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
    )
  }, [focusId, loading])

  const roleOf = useCallback(
    (status) => statuses.find((item) => String(item.id) === String(status))?.role,
    [statuses],
  )

  const filteredOrders = useMemo(() => {
    const text = search.trim().toLowerCase()
    return orders.filter((order) => {
      if (filter === 'open' && ['done', 'cancelled'].includes(roleOf(order.status))) return false
      if (filter !== 'all' && filter !== 'open' && String(order.status) !== filter) return false
      if (!text) return true
      const haystack = [
        `№${order.id}`, order.customer_name, order.customer_surname, order.customer_phone, order.note,
        ...order.items.map((item) => item.oil_name),
      ].join(' ').toLowerCase()
      return haystack.includes(text)
    })
  }, [filter, orders, roleOf, search])

  const filterOptions = useMemo(() => {
    const counts = orders.reduce((accumulator, order) => {
      const status = String(order.status)
      accumulator[status] = (accumulator[status] || 0) + 1
      return accumulator
    }, {})

    return Object.entries(counts).map(([status, count]) => ({
      status,
      count,
      label: statuses.find((item) => String(item.id) === status)?.name || status,
    }))
  }, [orders, statuses])

  const openCount = orders.filter((order) => !['done', 'cancelled'].includes(roleOf(order.status))).length

  const handleStatusChanged = (updated) => {
    setOrders((previous) =>
      previous.map((order) => (order.id === updated.id ? { ...order, status: updated.status } : order)),
    )
  }

  const handleDeleteOrder = async (id) => {
    if (!window.confirm(`Удалить заказ #${id}?`)) {
      return
    }

    try {
      await api.deleteOrder(id)
      await loadOrders()
    } catch (error) {
      alert(`Ошибка удаления: ${error.message}`)
    }
  }

  if (loading) {
    return <div className="state-panel">Загрузка заказов...</div>
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Заказы"
        title="Заказы"
        description="Позиции, прибыль и план производства по каждому заказу. Статус меняется прямо в карточке."
        actions={
          <Link to="/quick-order" className="ios-button primary">
            Записать заказ
          </Link>
        }
      />

      <input
        className="ios-input search-input"
        placeholder="Поиск: №, имя, телефон, масло…"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />

      <div className="filter-row filter-row--start">
        <button
          type="button"
          onClick={() => setFilter('open')}
          className={filter === 'open' ? 'filter-chip filter-chip--active' : 'filter-chip'}
        >
          Открытые ({openCount})
        </button>
        <button
          type="button"
          onClick={() => setFilter('all')}
          className={filter === 'all' ? 'filter-chip filter-chip--active' : 'filter-chip'}
        >
          Все ({orders.length})
        </button>
        {filterOptions.map((option) => (
          <button
            key={option.status}
            type="button"
            onClick={() => setFilter(option.status)}
            className={filter === option.status ? 'filter-chip filter-chip--active' : 'filter-chip'}
          >
            {option.label} ({option.count})
          </button>
        ))}
      </div>

      {filteredOrders.length === 0 ? (
        <div className="state-panel">Нет заказов для выбранного фильтра.</div>
      ) : (
        <div className="order-list">
          {filteredOrders.map((order) => (
            <article
              key={order.id}
              id={`order-${order.id}`}
              className={order.id === focusId ? 'order-card order-card--focus' : 'order-card'}
            >
              <div className="order-card__top">
                <div>
                  <div className="order-card__title-row">
                    <h2 className="order-card__title">Заказ №{order.id}</h2>
                    <StatusSelect orderId={order.id} status={order.status} onChanged={handleStatusChanged} />
                  </div>
                  <div className="order-card__customer">
                    <Link to={`/customers/${order.customer_id}`} className="crm-link crm-link--plain">
                      {order.customer_name} {order.customer_surname}
                    </Link>
                  </div>
                  <div className="order-card__meta">{order.customer_phone}</div>
                  <div className="order-card__meta">{order.customer_address}</div>
                  {order.note ? <div className="order-card__meta">{order.note}</div> : null}
                </div>

                <div className="order-card__summary">
                  <div className="order-card__price">
                    {(order.total_price || 0).toLocaleString('ru-RU')} ₽
                  </div>
                  <div className="order-card__meta">
                    Дата заказа: {order.date ? new Date(order.date).toLocaleDateString('ru-RU') : 'без даты'}
                  </div>
                  <div className="order-card__meta">
                    Отгрузка: {order.shipping_date ? new Date(order.shipping_date).toLocaleDateString('ru-RU') : 'без даты'}
                  </div>
                </div>
              </div>

              <ProductionPlan plan={order.production_plan} />

              <div className="order-card__body">
                {order.items.map((item) => (
                  <div key={`${order.id}_${item.oil_name}_${item.volume}`} className="order-card__line">
                    <span>
                      {item.oil_name}, {item.count}×{item.volume} мл
                    </span>
                    <span>{(item.revenue || item.price * item.count || 0).toLocaleString('ru-RU')} ₽</span>
                  </div>
                ))}

                <div className="order-card__line">
                  <span>Семена</span>
                  <span>
                    {totalOrderSeedWeight(order.items).toLocaleString('ru-RU', {
                      maximumFractionDigits: 3,
                    })}{' '}
                    кг
                  </span>
                </div>
                <div className="order-card__line">
                  <span>Прибыль</span>
                  <span>{totalOrderProfit(order.items).toLocaleString('ru-RU')} ₽</span>
                </div>
              </div>

              <div className="order-card__footer">
                <div className="order-card__meta">Позиций: {order.items.length}</div>
                <button
                  type="button"
                  onClick={() => handleDeleteOrder(order.id)}
                  className="link-danger"
                >
                  Удалить
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
