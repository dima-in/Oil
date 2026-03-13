import { useState, useEffect } from 'react'

const API_BASE = '/api'

export default function OrdersView() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    fetchOrders()
  }, [])

  const fetchOrders = async () => {
    try {
      const response = await fetch(`${API_BASE}/orders`)
      if (!response.ok) throw new Error('Failed to fetch')
      const data = await response.json()
      setOrders(data)
    } catch (error) {
      console.error('Error fetching orders:', error)
    } finally {
      setLoading(false)
    }
  }

  const deleteOrder = async (id) => {
    if (!confirm('Удалить заказ #' + id + '?')) return
    try {
      const response = await fetch(`${API_BASE}/order/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        }
      })
      if (!response.ok) throw new Error('Failed to delete')
      fetchOrders()
    } catch (error) {
      alert('Ошибка удаления: ' + error.message)
    }
  }

  const getStatusColor = (status) => {
    const colors = {
      '0': 'blue',
      '1': 'green',
      '2': 'purple',
      '3': 'orange',
      '4': 'green',
      '5': 'blue',
      '6': 'red',
      '7': 'orange'
    }
    return colors[status] || 'gray'
  }

  const getStatusLabel = (status) => {
    const labels = {
      '0': 'новый',
      '1': 'получена предоплата',
      '2': 'Avito доставка',
      '3': 'Ozon',
      '4': 'завершен',
      '5': 'готов к выдаче',
      '6': 'отменен',
      '7': 'ожидает предоплаты'
    }
    return labels[status] || status
  }

  const filteredOrders = filter === 'all' 
    ? orders 
    : orders.filter(o => o.status === filter)

  const uniqueStatuses = [...new Set(orders.map(o => o.status))]

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Загрузка заказов...</div>
  }

  return (
    <div className="animate-fade-in">
      <h1 className="text-3xl font-bold mb-6 bg-gradient-to-r from-green-400 to-green-600 bg-clip-text text-transparent">
        📋 Заказы
      </h1>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-all ${
            filter === 'all'
              ? 'bg-green-500/20 text-green-400'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          Все ({orders.length})
        </button>
        {uniqueStatuses.map(status => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-all ${
              filter === status
                ? 'bg-green-500/20 text-green-400'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {getStatusLabel(status)} ({orders.filter(o => o.status === status).length})
          </button>
        ))}
      </div>

      {/* Orders List */}
      <div className="space-y-3">
        {filteredOrders.length === 0 ? (
          <div className="ios-card text-center py-8 text-gray-400">
            Нет заказов
          </div>
        ) : (
          filteredOrders.map((order) => (
            <div key={order.id} className="ios-card">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg font-bold">Заказ #{order.id}</span>
                    <span className={`ios-badge ${getStatusColor(order.status)}`}>
                      {getStatusLabel(order.status)}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400">
                    {order.customer_name} {order.customer_surname} • {order.customer_phone}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-400">
                    {order.total_price?.toLocaleString() || 0} ₽
                  </div>
                  <div className="text-xs text-gray-400">
                    {new Date(order.date).toLocaleDateString('ru-RU')}
                  </div>
                </div>
              </div>

              <div className="border-t border-white/10 pt-3 mt-3">
                <div className="text-sm text-gray-400 mb-2">Товары:</div>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span>{order.oil_name} ({order.volume}мл)</span>
                    <span>{order.count} шт × {order.price} ₽ = {(order.count * order.price).toLocaleString()} ₽</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/10">
                <div className="text-xs text-gray-400">
                  📍 {order.customer_address}
                </div>
                <button
                  onClick={() => deleteOrder(order.id)}
                  className="text-red-400 hover:text-red-300 transition-colors text-sm"
                >
                  🗑️ Удалить
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
