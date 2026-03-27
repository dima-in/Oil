import { useEffect, useState } from 'react'
import { api } from '../lib/api'

function todayString() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function defaultRange() {
  return {
    dateFrom: `${todayString().slice(0, 8)}01`,
    dateTo: todayString(),
    period: 'month',
    dailyBatchLimit: 3,
  }
}

function defaultExpenseForm() {
  return {
    expense_date: todayString(),
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
  return {
    batch_date: todayString(),
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

function defaultProfileForm() {
  return {
    oil_name: '',
    batch_seed_weight_kg: '',
    yield_percent: '',
    daily_batch_limit: '3',
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
  const [profileForm, setProfileForm] = useState(defaultProfileForm)
  const [productionProfiles, setProductionProfiles] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const [analyticsData, profiles] = await Promise.all([
          api.getAnalytics(filters),
          api.getProductionProfiles(),
        ])
        setAnalytics(analyticsData)
        setProductionProfiles(profiles)
      } catch (error) {
        alert(`Ошибка загрузки аналитики: ${error.message}`)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [filters])

  const totals = analytics?.totals || {
    revenue: 0,
    net_profit: 0,
  }

  const batchAnalytics = analytics?.batch_analytics || {
    totals: {
      batches_count: 0,
      output_volume_ml: 0,
      sold_volume_ml: 0,
      remaining_volume_ml: 0,
      batch_cost: 0,
      realized_profit: 0,
    },
    batches: [],
    daily_batches: [],
  }

  const refresh = () => setFilters((previous) => ({ ...previous }))

  const handleSaveProfile = async (event) => {
    event.preventDefault()
    try {
      await api.saveProductionProfile({
        oil_name: profileForm.oil_name.trim(),
        batch_seed_weight_kg: Number(profileForm.batch_seed_weight_kg || 0),
        yield_percent: Number(profileForm.yield_percent || 0),
        daily_batch_limit: Number(profileForm.daily_batch_limit || 3),
        note: profileForm.note.trim(),
      })
      setProfileForm(defaultProfileForm())
      refresh()
    } catch (error) {
      alert(`Ошибка сохранения профиля: ${error.message}`)
    }
  }

  const handleDeleteProfile = async (id) => {
    if (!window.confirm('Удалить производственный профиль?')) {
      return
    }

    try {
      await api.deleteProductionProfile(id)
      refresh()
    } catch (error) {
      alert(`Ошибка удаления профиля: ${error.message}`)
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
      refresh()
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
      refresh()
    } catch (error) {
      alert(`Ошибка удаления закладки: ${error.message}`)
    }
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
      refresh()
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
      refresh()
    } catch (error) {
      alert(`Ошибка удаления расхода: ${error.message}`)
    }
  }

  if (loading && !analytics) {
    return <div className="state-panel">Загрузка аналитики...</div>
  }

  return (
    <div className="page-stack">
      <div className="section-head">
        <div>
          <h2 className="section-head__title">Прибыль и производство</h2>
          <p className="section-head__text">
            Здесь задаются производственные профили масел, фактические закладки и расходы.
            Профили используются для автоматического расчета количества закладок по заказам.
          </p>
        </div>
      </div>

      <form
        className="analytics-filters analytics-filters--wide"
        onSubmit={(event) => {
          event.preventDefault()
          refresh()
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
          onChange={(event) =>
            setFilters((prev) => ({ ...prev, dailyBatchLimit: Number(event.target.value) || 1 }))
          }
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

      <div className="section-head">
        <div>
          <h3 className="section-head__title">Производственные профили</h3>
          <p className="section-head__text">
            Один профиль на одно масло: стандартный вес закладки, процент выхода и лимит закладок в день.
          </p>
        </div>
      </div>

      <form onSubmit={handleSaveProfile} className="editor-grid editor-grid--profiles">
        <input
          type="text"
          placeholder="Масло"
          value={profileForm.oil_name}
          onChange={(event) => setProfileForm((prev) => ({ ...prev, oil_name: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          step="0.001"
          placeholder="Вес закладки, кг"
          value={profileForm.batch_seed_weight_kg}
          onChange={(event) =>
            setProfileForm((prev) => ({ ...prev, batch_seed_weight_kg: event.target.value }))
          }
          className="ios-input"
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Выход, %"
          value={profileForm.yield_percent}
          onChange={(event) => setProfileForm((prev) => ({ ...prev, yield_percent: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="number"
          min="1"
          max="24"
          placeholder="Лимит в день"
          value={profileForm.daily_batch_limit}
          onChange={(event) => setProfileForm((prev) => ({ ...prev, daily_batch_limit: event.target.value }))}
          className="ios-input"
          required
        />
        <input
          type="text"
          placeholder="Комментарий"
          value={profileForm.note}
          onChange={(event) => setProfileForm((prev) => ({ ...prev, note: event.target.value }))}
          className="ios-input"
        />
        <button type="submit" className="ios-button success">
          Сохранить профиль
        </button>
      </form>

      <div className="table-wrap">
        <table className="price-table">
          <thead>
            <tr>
              <th>Масло</th>
              <th>Вес закладки, кг</th>
              <th>Выход, %</th>
              <th>Объем с закладки, мл</th>
              <th>Лимит в день</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {productionProfiles.map((item) => (
              <tr key={item.id}>
                <td>{item.oil_name}</td>
                <td>{(item.batch_seed_weight_kg || 0).toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</td>
                <td>{(item.yield_percent || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}</td>
                <td>{((item.batch_seed_weight_kg || 0) * (item.yield_percent || 0) * 10).toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</td>
                <td>{item.daily_batch_limit}</td>
                <td>
                  <button type="button" onClick={() => handleDeleteProfile(item.id)} className="link-danger">
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
