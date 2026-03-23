import { useEffect, useMemo, useState } from 'react'
import PageHeader from './PageHeader'
import StatusBadge from './StatusBadge'
import { api } from '../lib/api'
import { STATUS_MAP } from '../lib/constants'

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
        description="По каждому заказу видно выручку, расход семян и прибыль по позиции."
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
            <article key={`${order.id}_${order.oil_name}_${order.volume}`} className="order-card">
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
                </div>

                <div className="order-card__summary">
                  <div className="order-card__price">
                    {(order.total_price || 0).toLocaleString('ru-RU')} ₽
                  </div>
                  <div className="order-card__meta">
                    {order.date ? new Date(order.date).toLocaleDateString('ru-RU') : 'Без даты'}
                  </div>
                </div>
              </div>

              <div className="order-card__body">
                <div className="order-card__line">
                  <span>{order.oil_name}</span>
                  <span>{order.volume} мл</span>
                </div>
                <div className="order-card__line">
                  <span>{order.count} шт.</span>
                  <span>{(order.revenue || 0).toLocaleString('ru-RU')} ₽</span>
                </div>
                <div className="order-card__line">
                  <span>Семена</span>
                  <span>
                    {(Number(order.seed_weight_kg || 0) * Number(order.count || 0)).toLocaleString('ru-RU', {
                      maximumFractionDigits: 3,
                    })}{' '}
                    кг
                  </span>
                </div>
                <div className="order-card__line">
                  <span>Прибыль</span>
                  <span>{(order.profit || 0).toLocaleString('ru-RU')} ₽</span>
                </div>
              </div>

              <div className="order-card__footer">
                <div className="order-card__meta">{order.customer_address}</div>
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
