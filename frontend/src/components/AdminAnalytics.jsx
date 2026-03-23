import { useEffect, useState } from 'react'
import { api } from '../lib/api'

function defaultRange() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return {
    dateFrom: `${year}-${month}-01`,
    dateTo: `${year}-${month}-${day}`,
    period: 'month',
    dailyBatchLimit: 3,
  }
}

function defaultExpenseForm() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return {
    expense_date: `${year}-${month}-${day}`,
    item_name: '',
    weight_kg: '',
    price_per_kg: '',
    goods_total: '',
    delivery_cost: '',
    carsharing_cost: '',
    note: '',
  }
}

function defaultBatchForm() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return {
    batch_date: `${year}-${month}-${day}`,
    oil_name: '',
    seed_weight_kg: '',
    seed_price_per_kg: '',
    yield_percent: '',
    output_volume_ml: '',
    labor_cost: '',
    packaging_cost: '',
    other_cost: '',
    note: '',
  }
}

function MetricCard({ label, value, suffix = '' }) {
  return (
    <div className="metric-card">
      <div className="metric-card__label">{label}</div>
      <div className="metric-card__value">
        {value}
        {suffix}
      </div>
    </div>
  )
}

export default function AdminAnalytics() {
  const [filters, setFilters] = useState(defaultRange)
  const [expenseForm, setExpenseForm] = useState(defaultExpenseForm)
  const [batchForm, setBatchForm] = useState(defaultBatchForm)
  const [loading, setLoading] = useState(true)
  const [analytics, setAnalytics] = useState(null)

  useEffect(() => {
    async function loadAnalytics() {
      try {
        setLoading(true)
        const data = await api.getAnalytics(filters)
        setAnalytics(data)
      } catch (error) {
        alert(`Ошибка загрузки аналитики: ${error.message}`)
      } finally {
        setLoading(false)
      }
    }

    loadAnalytics()
  }, [filters])

  const totals = analytics?.totals || {
    orders_count: 0,
    revenue: 0,
    seed_cost: 0,
    profit: 0,
    seed_weight_kg: 0,
    extra_expense: 0,
    net_profit: 0,
    purchased_weight_kg: 0,
  }

  const batchAnalytics = analytics?.batch_analytics || {
    totals: {
      batches_count: 0,
      output_volume_ml: 0,
      sold_volume_ml: 0,
      remaining_volume_ml: 0,
      batch_cost: 0,
      allocated_revenue: 0,
      realized_profit: 0,
    },
    batches: [],
    daily_batches: [],
    daily_batch_limit: filters.dailyBatchLimit,
  }

  const handleAddExpense = async (event) => {
    event.preventDefault()
    try {
      const weight = Number(expenseForm.weight_kg || 0)
      const price = Number(expenseForm.price_per_kg || 0)
      const goodsTotal =
        expenseForm.goods_total === '' ? weight * price : Number(expenseForm.goods_total || 0)

      await api.addExpense({
        ...expenseForm,
        weight_kg: weight,
        price_per_kg: price,
        goods_total: goodsTotal,
        delivery_cost: Number(expenseForm.delivery_cost || 0),
        carsharing_cost: Number(expenseForm.carsharing_cost || 0),
      })
      setExpenseForm(defaultExpenseForm())
      setFilters((previous) => ({ ...previous }))
    } catch (error) {
      alert(`Ошибка сохранения расхода: ${error.message}`)
    }
  }

  const handleDeleteExpense = async (id) => {
    if (!window.confirm('Удалить запись расхода?')) {
      return
    }

    try {
      await api.deleteExpense(id)
      setFilters((previous) => ({ ...previous }))
    } catch (error) {
      alert(`Ошибка удаления расхода: ${error.message}`)
    }
  }

  const handleAddBatch = async (event) => {
    event.preventDefault()
    try {
      const seedWeight = Number(batchForm.seed_weight_kg || 0)
      const yieldPercent = Number(batchForm.yield_percent || 0)
      const outputVolume =
        batchForm.output_volume_ml === ''
          ? seedWeight * yieldPercent * 10
          : Number(batchForm.output_volume_ml || 0)

      await api.addProductionBatch({
        ...batchForm,
        seed_weight_kg: seedWeight,
        seed_price_per_kg: Number(batchForm.seed_price_per_kg || 0),
        yield_percent: yieldPercent,
        output_volume_ml: outputVolume,
        labor_cost: Number(batchForm.labor_cost || 0),
        packaging_cost: Number(batchForm.packaging_cost || 0),
        other_cost: Number(batchForm.other_cost || 0),
      })
      setBatchForm(defaultBatchForm())
      setFilters((previous) => ({ ...previous }))
    } catch (error) {
      alert(`Ошибка сохранения закладки: ${error.message}`)
    }
  }

  const handleDeleteBatch = async (id) => {
    if (!window.confirm('Удалить закладку?')) {
      return
    }

    try {
      await api.deleteProductionBatch(id)
      setFilters((previous) => ({ ...previous }))
    } catch (error) {
      alert(`Ошибка удаления закладки: ${error.message}`)
    }
  }

  if (loading && !analytics) {
    return <div className="state-panel">Загрузка аналитики...</div>
  }

  return (
    <div className="page-stack">
      <div className="section-head">
        <div>
          <h2 className="section-head__title">Прибыль и закладки</h2>
          <p className="section-head__text">
            Прибыль считается не только по продажам, но и по производственным закладкам: сырье, процент выхода, полученный объём и продажи из партии по FIFO.
          </p>
        </div>
      </div>

      <form
        className="analytics-filters analytics-filters--wide"
        onSubmit={(event) => {
          event.preventDefault()
          setFilters((previous) => ({ ...previous }))
        }}
      >
        <select
          value={filters.period}
          onChange={(event) => setFilters((prev) => ({ ...prev, period: event.target.value }))}
          className="ios-input"
        >
          <option value="day">По дням</option>
          <option value="week">По неделям</option>
          <option value="month">По месяцам</option>
        </select>
        <input
          type="date"
          value={filters.dateFrom}
          onChange={(event) => setFilters((prev) => ({ ...prev, dateFrom: event.target.value }))}
          className="ios-input"
        />
        <input
          type="date"
          value={filters.dateTo}
          onChange={(event) => setFilters((prev) => ({ ...prev, dateTo: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          min="1"
          max="24"
          value={filters.dailyBatchLimit}
          onChange={(event) => setFilters((prev) => ({ ...prev, dailyBatchLimit: Number(event.target.value) || 1 }))}
          className="ios-input"
          placeholder="Лимит закладок в день"
        />
        <button type="submit" className="ios-button">
          Обновить
        </button>
      </form>

      <div className="metrics-grid">
        <MetricCard label="Выручка" value={(totals.revenue || 0).toLocaleString('ru-RU')} suffix=" ₽" />
        <MetricCard label="Чистая прибыль" value={(totals.net_profit || 0).toLocaleString('ru-RU')} suffix=" ₽" />
        <MetricCard label="Закладки" value={batchAnalytics.totals.batches_count || 0} />
        <MetricCard label="Получено масла" value={(batchAnalytics.totals.output_volume_ml || 0).toLocaleString('ru-RU')} suffix=" мл" />
        <MetricCard label="Продано из закладок" value={(batchAnalytics.totals.sold_volume_ml || 0).toLocaleString('ru-RU')} suffix=" мл" />
        <MetricCard label="Остаток в закладках" value={(batchAnalytics.totals.remaining_volume_ml || 0).toLocaleString('ru-RU')} suffix=" мл" />
        <MetricCard label="Себестоимость закладок" value={(batchAnalytics.totals.batch_cost || 0).toLocaleString('ru-RU')} suffix=" ₽" />
        <MetricCard label="Реализованная прибыль по закладкам" value={(batchAnalytics.totals.realized_profit || 0).toLocaleString('ru-RU')} suffix=" ₽" />
      </div>

      <form onSubmit={handleAddBatch} className="editor-grid editor-grid--batches">
        <input
          type="date"
          value={batchForm.batch_date}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, batch_date: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="text"
          placeholder="Масло"
          value={batchForm.oil_name}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, oil_name: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          step="0.001"
          placeholder="Сырье, кг"
          value={batchForm.seed_weight_kg}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, seed_weight_kg: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Цена сырья, ₽/кг"
          value={batchForm.seed_price_per_kg}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, seed_price_per_kg: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Выход, %"
          value={batchForm.yield_percent}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, yield_percent: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Выход масла, мл"
          value={batchForm.output_volume_ml}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, output_volume_ml: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          step="0.01"
          placeholder="Труд, ₽"
          value={batchForm.labor_cost}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, labor_cost: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          step="0.01"
          placeholder="Упаковка, ₽"
          value={batchForm.packaging_cost}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, packaging_cost: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          step="0.01"
          placeholder="Прочее, ₽"
          value={batchForm.other_cost}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, other_cost: event.target.value }))}
          className="ios-input"
        />
        <input
          type="text"
          placeholder="Комментарий"
          value={batchForm.note}
          onChange={(event) => setBatchForm((prev) => ({ ...prev, note: event.target.value }))}
          className="ios-input"
        />
        <button type="submit" className="ios-button success">
          Добавить закладку
        </button>
      </form>

      <div className="table-wrap">
        <table className="price-table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Масло</th>
              <th>Сырье, кг</th>
              <th>Выход, %</th>
              <th>Масло, мл</th>
              <th>Продано, мл</th>
              <th>Остаток, мл</th>
              <th>Себестоимость</th>
              <th>Прибыль</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {(batchAnalytics.batches || []).map((item) => (
              <tr key={item.id}>
                <td>{item.batch_date}</td>
                <td>{item.oil_name}</td>
                <td>{(item.seed_weight_kg || 0).toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</td>
                <td>{(item.yield_percent || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}</td>
                <td>{(item.output_volume_ml || 0).toLocaleString('ru-RU')}</td>
                <td>{(item.sold_volume_ml || 0).toLocaleString('ru-RU')}</td>
                <td>{(item.remaining_volume_ml || 0).toLocaleString('ru-RU')}</td>
                <td>{(item.batch_cost || 0).toLocaleString('ru-RU')} ₽</td>
                <td>{(item.realized_profit || 0).toLocaleString('ru-RU')} ₽</td>
                <td>
                  <button type="button" onClick={() => handleDeleteBatch(item.id)} className="link-danger">
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-wrap">
        <table className="price-table">
          <thead>
            <tr>
              <th>День</th>
              <th>Закладок</th>
              <th>Лимит</th>
              <th>Загрузка, %</th>
              <th>Свободно</th>
              <th>Масло, мл</th>
              <th>Прибыль</th>
            </tr>
          </thead>
          <tbody>
            {(batchAnalytics.daily_batches || []).map((item) => (
              <tr key={item.date}>
                <td>{item.date}</td>
                <td>{item.batches_count}</td>
                <td>{item.daily_batch_limit}</td>
                <td>{(item.capacity_used_percent || 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</td>
                <td>{item.remaining_slots}</td>
                <td>{(item.output_volume_ml || 0).toLocaleString('ru-RU')}</td>
                <td>{(item.realized_profit || 0).toLocaleString('ru-RU')} ₽</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form onSubmit={handleAddExpense} className="editor-grid editor-grid--expenses">
        <input
          type="date"
          value={expenseForm.expense_date}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, expense_date: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="text"
          placeholder="Наименование"
          value={expenseForm.item_name}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, item_name: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          placeholder="Кг"
          step="0.001"
          value={expenseForm.weight_kg}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, weight_kg: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          placeholder="Цена за 1 кг"
          step="0.01"
          value={expenseForm.price_per_kg}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, price_per_kg: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          placeholder="Сумма заказа"
          step="0.01"
          value={expenseForm.goods_total}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, goods_total: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          placeholder="Доставка"
          step="0.01"
          value={expenseForm.delivery_cost}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, delivery_cost: event.target.value }))}
          className="ios-input"
        />
        <input
          type="number"
          placeholder="Каршеринг"
          step="0.01"
          value={expenseForm.carsharing_cost}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, carsharing_cost: event.target.value }))}
          className="ios-input"
        />
        <input
          type="text"
          placeholder="Комментарий"
          value={expenseForm.note}
          onChange={(event) => setExpenseForm((prev) => ({ ...prev, note: event.target.value }))}
          className="ios-input"
        />
        <button type="submit" className="ios-button success">
          Добавить расход
        </button>
      </form>

      <div className="table-wrap">
        <table className="price-table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Наименование</th>
              <th>Кг</th>
              <th>Цена за 1 кг</th>
              <th>Сумма заказа</th>
              <th>Доставка</th>
              <th>Каршеринг</th>
              <th>Итого</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {(analytics?.expenses || []).map((item) => (
              <tr key={item.id}>
                <td>{item.expense_date}</td>
                <td>{item.item_name}</td>
                <td>{(item.weight_kg || 0).toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</td>
                <td>{(item.price_per_kg || 0).toLocaleString('ru-RU')} ₽</td>
                <td>{(item.goods_total || 0).toLocaleString('ru-RU')} ₽</td>
                <td>{(item.delivery_cost || 0).toLocaleString('ru-RU')} ₽</td>
                <td>{(item.carsharing_cost || 0).toLocaleString('ru-RU')} ₽</td>
                <td>{(item.total_expense || 0).toLocaleString('ru-RU')} ₽</td>
                <td>
                  <button type="button" onClick={() => handleDeleteExpense(item.id)} className="link-danger">
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
