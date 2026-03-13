import { useState, useEffect } from 'react'

const API_BASE = '/api'

export default function PricelistManager() {
  const [prices, setPrices] = useState([])
  const [loading, setLoading] = useState(true)
  const [newItem, setNewItem] = useState({ oil_name: '', volume: '', price: '' })
  const [editingId, setEditingId] = useState(null)

  useEffect(() => {
    fetchPrices()
  }, [])

  const fetchPrices = async () => {
    try {
      const response = await fetch(`${API_BASE}/admin/pricelist`)
      if (!response.ok) throw new Error('Failed to fetch')
      const data = await response.json()
      setPrices(data)
    } catch (error) {
      console.error('Error fetching prices:', error)
    } finally {
      setLoading(false)
    }
  }

  const updatePrice = async (id, newPrice) => {
    try {
      const response = await fetch(`${API_BASE}/admin/pricelist/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        },
        body: JSON.stringify({ price: newPrice })
      })
      if (!response.ok) throw new Error('Failed to update')
      fetchPrices()
    } catch (error) {
      alert('Ошибка обновления: ' + error.message)
    }
  }

  const deletePrice = async (id) => {
    if (!confirm('Удалить этот товар?')) return
    try {
      const response = await fetch(`${API_BASE}/admin/pricelist/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        }
      })
      if (!response.ok) throw new Error('Failed to delete')
      fetchPrices()
    } catch (error) {
      alert('Ошибка удаления: ' + error.message)
    }
  }

  const addPriceItem = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch(`${API_BASE}/admin/pricelist`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        },
        body: JSON.stringify(newItem)
      })
      if (!response.ok) throw new Error('Failed to add')
      setNewItem({ oil_name: '', volume: '', price: '' })
      fetchPrices()
    } catch (error) {
      alert('Ошибка добавления: ' + error.message)
    }
  }

  const clearPricelist = async () => {
    if (!confirm('Вы уверены? Это удалит ВСЕ товары из прайс-листа!')) return
    try {
      const response = await fetch(`${API_BASE}/admin/pricelist/clear`, {
        method: 'POST',
        headers: {
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        }
      })
      if (!response.ok) throw new Error('Failed to clear')
      fetchPrices()
    } catch (error) {
      alert('Ошибка очистки: ' + error.message)
    }
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Загрузка...</div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">📦 Управление ценами</h2>
        <button onClick={clearPricelist} className="ios-button danger text-sm">
          Очистить всё
        </button>
      </div>

      {/* Add New Item Form */}
      <form onSubmit={addPriceItem} className="mb-6 p-4 bg-white/5 rounded-lg">
        <h3 className="text-sm font-semibold mb-3 text-gray-400">Добавить товар</h3>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            placeholder="Название масла"
            value={newItem.oil_name}
            onChange={(e) => setNewItem({...newItem, oil_name: e.target.value})}
            className="ios-input flex-1 min-w-[150px]"
            required
          />
          <input
            type="number"
            placeholder="Объём (мл)"
            value={newItem.volume}
            onChange={(e) => setNewItem({...newItem, volume: e.target.value})}
            className="ios-input w-24"
            required
          />
          <input
            type="number"
            placeholder="Цена (₽)"
            value={newItem.price}
            onChange={(e) => setNewItem({...newItem, price: e.target.value})}
            className="ios-input w-28"
            step="0.01"
            required
          />
          <button type="submit" className="ios-button success">
            + Добавить
          </button>
        </div>
      </form>

      {/* Prices Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-sm text-gray-400 border-b border-white/10">
              <th className="pb-3 font-medium">ID</th>
              <th className="pb-3 font-medium">Название</th>
              <th className="pb-3 font-medium">Объём</th>
              <th className="pb-3 font-medium">Цена</th>
              <th className="pb-3 font-medium">Действия</th>
            </tr>
          </thead>
          <tbody>
            {prices.length === 0 ? (
              <tr>
                <td colSpan="5" className="py-8 text-center text-gray-400">
                  Прайс-лист пуст
                </td>
              </tr>
            ) : (
              prices.map((item) => (
                <tr key={item.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="py-3 text-sm text-gray-400">#{item.id}</td>
                  <td className="py-3 font-medium">{item.oil_name}</td>
                  <td className="py-3">{item.volume} мл</td>
                  <td className="py-3">
                    {editingId === item.id ? (
                      <input
                        type="number"
                        defaultValue={item.price}
                        className="ios-input w-28 inline-block"
                        autoFocus
                        onBlur={(e) => {
                          updatePrice(item.id, parseFloat(e.target.value))
                          setEditingId(null)
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            updatePrice(item.id, parseFloat(e.currentTarget.value))
                            setEditingId(null)
                          }
                        }}
                      />
                    ) : (
                      <span 
                        onClick={() => setEditingId(item.id)}
                        className="cursor-pointer hover:text-blue-400 transition-colors"
                      >
                        {item.price} ₽
                      </span>
                    )}
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => deletePrice(item.id)}
                      className="text-red-400 hover:text-red-300 transition-colors text-sm"
                    >
                      🗑️ Удалить
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
