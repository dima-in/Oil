import { useEffect, useMemo, useState } from 'react'
import PageHeader from './PageHeader'
import StatusBadge from './StatusBadge'
import { api } from '../lib/api'
import { STATUS_MAP } from '../lib/constants'

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
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    loadOrders()
  }, [])

  const loadOrders = async () => {
    try {
      const data = await api.getOrders()
      setOrders(data)
    } catch (error) {
      console.error('Error fetching orders:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredOrders = useMemo(() => {
    if (filter === 'all') {
      return orders
    }

    return orders.filter((order) => String(order.status) === filter)
  }, [filter, orders])

  const filterOptions = useMemo(() => {
    const counts = orders.reduce((accumulator, order) => {
      const status = String(order.status)
      accumulator[status] = (accumulator[status] || 0) + 1
      return accumulator
    }, {})

    return Object.entries(counts).map(([status, count]) => ({
      status,
      count,
      label: STATUS_MAP[status]?.label || status,
    }))
  }, [orders])

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
        eyebrow="История"
        title="Заказы"
        description="По каждому заказу видны позиции, прибыль и краткий план производства по маслам."
      />

      <div className="filter-row">
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
            <article key={order.id} className="order-card">
              <div className="order-card__top">
                <div>
                  <div className="order-card__title-row">
                    <h2 className="order-card__title">Заказ #{order.id}</h2>
                    <StatusBadge status={order.status} />
                  </div>
                  <div className="order-card__customer">
                    {order.customer_name} {order.customer_surname}
                  </div>
                  <div className="order-card__meta">{order.customer_phone}</div>
                  <div className="order-card__meta">{order.customer_address}</div>
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
                    <span>{(item.revenue || 0).toLocaleString('ru-RU')} ₽</span>
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
