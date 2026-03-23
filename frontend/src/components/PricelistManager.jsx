import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const emptyItem = {
  oil_name: '',
  volume: '',
  price: '',
  seed_weight_kg: '',
  seed_price_per_kg: '',
}

export default function PricelistManager() {
  const [prices, setPrices] = useState([])
  const [loading, setLoading] = useState(true)
  const [newItem, setNewItem] = useState(emptyItem)
  const [editingId, setEditingId] = useState(null)
  const [editItem, setEditItem] = useState(emptyItem)

  useEffect(() => {
    loadPrices()
  }, [])

  const loadPrices = async () => {
    try {
      const data = await api.getPricelist()
      setPrices(data)
    } catch (error) {
      console.error('Error fetching prices:', error)
    } finally {
      setLoading(false)
    }
  }

  const startEdit = (item) => {
    setEditingId(item.id)
    setEditItem({
      oil_name: item.oil_name,
      volume: String(item.volume),
      price: String(item.price),
      seed_weight_kg: String(item.seed_weight_kg || 0),
      seed_price_per_kg: String(item.seed_price_per_kg || 0),
    })
  }

  const handleUpdatePrice = async (id) => {
    try {
      await api.updatePrice(id, {
        oil_name: editItem.oil_name,
        volume: Number(editItem.volume),
        price: Number(editItem.price),
        seed_weight_kg: Number(editItem.seed_weight_kg || 0),
        seed_price_per_kg: Number(editItem.seed_price_per_kg || 0),
      })
      await loadPrices()
      setEditingId(null)
      setEditItem(emptyItem)
    } catch (error) {
      alert(`Ошибка обновления: ${error.message}`)
    }
  }

  const handleDeletePrice = async (id) => {
    if (!window.confirm('Удалить этот товар?')) {
      return
    }

    try {
      await api.deletePrice(id)
      await loadPrices()
    } catch (error) {
      alert(`Ошибка удаления: ${error.message}`)
    }
  }

  const handleAddPriceItem = async (event) => {
    event.preventDefault()

    try {
      await api.addPriceItem({
        ...newItem,
        volume: Number(newItem.volume),
        price: Number(newItem.price),
        seed_weight_kg: Number(newItem.seed_weight_kg || 0),
        seed_price_per_kg: Number(newItem.seed_price_per_kg || 0),
      })
      setNewItem(emptyItem)
      await loadPrices()
    } catch (error) {
      alert(`Ошибка добавления: ${error.message}`)
    }
  }

  const handleClearPricelist = async () => {
    if (!window.confirm('Очистить весь прайс-лист?')) {
      return
    }

    try {
      await api.clearPricelist()
      await loadPrices()
    } catch (error) {
      alert(`Ошибка очистки: ${error.message}`)
    }
  }

  if (loading) {
    return <div className="state-panel">Загрузка прайс-листа...</div>
  }

  return (
    <div className="page-stack">
      <div className="section-head">
        <div>
          <h2 className="section-head__title">Управление ценами и семенами</h2>
          <p className="section-head__text">
            Для каждого SKU можно задать цену, расход семян на единицу товара и цену закупки семян за кг.
          </p>
        </div>
        <button type="button" onClick={handleClearPricelist} className="ios-button danger">
          Очистить все
        </button>
      </div>

      <form onSubmit={handleAddPriceItem} className="editor-grid editor-grid--wide">
        <input
          type="text"
          placeholder="Название масла"
          value={newItem.oil_name}
          onChange={(event) => setNewItem((previous) => ({ ...previous, oil_name: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          placeholder="Объем, мл"
          value={newItem.volume}
          onChange={(event) => setNewItem((previous) => ({ ...previous, volume: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          placeholder="Цена, ₽"
          value={newItem.price}
          onChange={(event) => setNewItem((previous) => ({ ...previous, price: event.target.value }))}
          className="ios-input"
          step="0.01"
          required
        />
        <input
          type="number"
          placeholder="Семена на 1 шт, кг"
          value={newItem.seed_weight_kg}
          onChange={(event) => setNewItem((previous) => ({ ...previous, seed_weight_kg: event.target.value }))}
          className="ios-input"
          step="0.001"
        />
        <input
          type="number"
          placeholder="Цена семян, ₽/кг"
          value={newItem.seed_price_per_kg}
          onChange={(event) => setNewItem((previous) => ({ ...previous, seed_price_per_kg: event.target.value }))}
          className="ios-input"
          step="0.01"
        />
        <button type="submit" className="ios-button success">
          Добавить
        </button>
      </form>

      <div className="table-wrap">
        <table className="price-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Название</th>
              <th>Объем</th>
              <th>Цена</th>
              <th>Семена, кг/шт</th>
              <th>Цена семян, ₽/кг</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {prices.length === 0 ? (
              <tr>
                <td colSpan="7" className="price-table__empty">
                  Прайс-лист пуст.
                </td>
              </tr>
            ) : (
              prices.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td>
                    {editingId === item.id ? (
                      <input
                        type="text"
                        value={editItem.oil_name}
                        onChange={(event) => setEditItem((prev) => ({ ...prev, oil_name: event.target.value }))}
                        className="ios-input"
                      />
                    ) : (
                      item.oil_name
                    )}
                  </td>
                  <td>
                    {editingId === item.id ? (
                      <input
                        type="number"
                        value={editItem.volume}
                        onChange={(event) => setEditItem((prev) => ({ ...prev, volume: event.target.value }))}
                        className="ios-input"
                      />
                    ) : (
                      `${item.volume} мл`
                    )}
                  </td>
                  <td>
                    {editingId === item.id ? (
                      <input
                        type="number"
                        value={editItem.price}
                        onChange={(event) => setEditItem((prev) => ({ ...prev, price: event.target.value }))}
                        className="ios-input"
                        step="0.01"
                      />
                    ) : (
                      `${item.price} ₽`
                    )}
                  </td>
                  <td>
                    {editingId === item.id ? (
                      <input
                        type="number"
                        value={editItem.seed_weight_kg}
                        onChange={(event) => setEditItem((prev) => ({ ...prev, seed_weight_kg: event.target.value }))}
                        className="ios-input"
                        step="0.001"
                      />
                    ) : (
                      item.seed_weight_kg || 0
                    )}
                  </td>
                  <td>
                    {editingId === item.id ? (
                      <input
                        type="number"
                        value={editItem.seed_price_per_kg}
                        onChange={(event) => setEditItem((prev) => ({ ...prev, seed_price_per_kg: event.target.value }))}
                        className="ios-input"
                        step="0.01"
                      />
                    ) : (
                      `${item.seed_price_per_kg || 0} ₽`
                    )}
                  </td>
                  <td className="table-actions">
                    {editingId === item.id ? (
                      <>
                        <button type="button" onClick={() => handleUpdatePrice(item.id)} className="link-button">
                          Сохранить
                        </button>
                        <button type="button" onClick={() => setEditingId(null)} className="link-danger">
                          Отмена
                        </button>
                      </>
                    ) : (
                      <>
                        <button type="button" onClick={() => startEdit(item)} className="link-button">
                          Изменить
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeletePrice(item.id)}
                          className="link-danger"
                        >
                          Удалить
                        </button>
                      </>
                    )}
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
