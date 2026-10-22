import { useState } from 'react'
import { api } from '../lib/api'
import { notifyDataChanged } from '../lib/events'
import { dateRu, money } from '../lib/format'
import { MonthlyRevenueChart } from './RevenueByMonth'

// Импорт старой таблицы заказов: сначала проверка (ничего не пишет), потом загрузка.
export default function ImportOrdersPanel({ isAdmin }) {
  const [file, setFile] = useState(null)
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [imported, setImported] = useState(null)

  const send = async (commit) => {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const result = await api.importOrders(file, commit)
      setReport(result)
      if (commit) {
        setImported({
          orders: result.imported,
          expenses: result.imported_expenses || 0,
          norms: result.applied_norms || 0,
        })
        notifyDataChanged()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-stack page-stack--compact">
      <div className="section-head">
        <div>
          <h3 className="section-head__title">Импорт старых заказов из Excel</h3>
          <p className="section-head__text">
            Таблица вида «Выжимальня.xlsx»: лист «Заказы» (даты, масла по колонкам, ФИО, доставка) и лист «Прайс».
            Сначала проверка — ничего не записывается. Заказы, которые уже есть в CRM (та же дата ±3 дня и тот же
            набор бутылок), пропускаются, поэтому повторная загрузка ничего не задвоит.
          </p>
        </div>
      </div>

      {!isAdmin ? <div className="muted">Загружать заказы может администратор.</div> : null}

      <div className="inline-form">
        <input
          className="ios-input"
          type="file"
          accept=".xlsx,.xlsm"
          onChange={(event) => {
            setFile(event.target.files?.[0] || null)
            setReport(null)
            setImported(null)
          }}
          disabled={!isAdmin || busy}
        />
        <button type="button" className="ios-button secondary" disabled={!file || busy || !isAdmin} onClick={() => send(false)}>
          {busy && !report ? 'Проверяю…' : 'Проверить'}
        </button>
      </div>

      {error ? <div className="notice notice--error">{error}</div> : null}
      {imported !== null ? (
        <div className="notice notice--success">
          Загружено: заказов {imported.orders}, закупок в «Расходы» {imported.expenses}, норм себестоимости{' '}
          {imported.norms}. Заказы — в «Заказах» и выручке по месяцам, маржа — во вкладке «Экономика».
        </div>
      ) : null}

      {report ? (
        <>
          <div className="kpi-grid">
            <div className="kpi">
              <div className="kpi__label">Заказов в файле</div>
              <div className="kpi__value">{report.orders_in_file}</div>
              <div className="kpi__hint">итоговых строк пропущено: {report.skipped_rows}</div>
            </div>
            <div className="kpi">
              <div className="kpi__label">Уже есть в CRM</div>
              <div className="kpi__value">{report.duplicates}</div>
              <div className="kpi__hint">не загружаются</div>
            </div>
            <div className="kpi">
              <div className="kpi__label">К загрузке</div>
              <div className="kpi__value">{report.to_import}</div>
              <div className="kpi__hint">
                новых клиентов: {report.new_customers}; открытых заказов: {report.open_orders}
              </div>
            </div>
            <div className="kpi">
              <div className="kpi__label">Выручка по файлу</div>
              <div className="kpi__value">{money(report.revenue_total)}</div>
              <div className="kpi__hint">цены: {report.price_source}</div>
            </div>
          </div>

          {report.approx_orders || report.unpriced_orders ? (
            <div className="notice notice--warning">
              {report.approx_orders ? (
                <div>
                  {report.approx_orders} заказ(ов) с нестандартным объёмом (170, 380 мл…) — посчитаны по цене за мл
                  ближайшей бутылки.
                </div>
              ) : null}
              {report.unpriced_orders ? (
                <div>
                  {report.unpriced_orders} заказ(ов) с маслом без цены в прайсе (например, чёрный кунжут, грецкий орех)
                  — эти позиции идут по 0 ₽, поправьте цену в заказе при необходимости.
                </div>
              ) : null}
            </div>
          ) : null}

          <MonthlyRevenueChart
            rows={report.months.map((month) => ({ ...month, avg_check: month.orders ? month.revenue / month.orders : 0 }))}
            note="Оценка по прайсу из файла: в строках старой таблицы цены не записаны, а прайс со временем менялся. Допы (урбеч, жмых, мука) в сумму не входят."
          />

          {report.economics?.oils?.length ? (
            <details className="chat-details" open>
              <summary>
                Нормы себестоимости с листа «Прайс»: {report.economics.oils.length} масел
                {report.economics.oils.some((oil) => oil.changed)
                  ? ` (изменятся: ${report.economics.oils.filter((oil) => oil.changed).length})`
                  : ' (совпадают с CRM)'}
              </summary>
              <p className="page-hint">
                Бутылка {report.economics.settings.bottle_cost ?? '—'} ₽, доставка семян{' '}
                {report.economics.settings.seed_delivery_per_kg ?? '—'} ₽/кг, налог {report.economics.settings.tax_percent ?? '—'}%.
                Из этого CRM считает маржу каждой бутылки («Управление → Экономика»).
              </p>
              <div className="table-wrap">
                <table className="price-table price-table--compact crm-table">
                  <thead>
                    <tr>
                      <th>Масло</th>
                      <th className="num">Кг в закладке</th>
                      <th className="num">Выход, мл</th>
                      <th className="num">Семена, ₽/кг</th>
                      <th className="num">Получка за закладку</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {report.economics.oils.map((oil) => (
                      <tr key={oil.oil_name}>
                        <td>{oil.oil_name}</td>
                        <td className="num">{oil.kg_per_batch}</td>
                        <td className="num">{oil.yield_ml}</td>
                        <td className="num">{oil.seed_price_per_kg ?? '—'}</td>
                        <td className="num">{oil.labor_per_batch ? money(oil.labor_per_batch) : '—'}</td>
                        <td>{oil.changed ? <span className="tag tag--source">новое</span> : null}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}

          {report.expenses?.in_file ? (
            <details className="chat-details" open>
              <summary>
                Закупки с листа «Прибыль и убыль»: {report.expenses.in_file}, новых {report.expenses.new} на{' '}
                {money(report.expenses.total_new)}
                {report.expenses.duplicates ? `, уже в «Расходах»: ${report.expenses.duplicates}` : ''}
              </summary>
              <div className="table-wrap">
                <table className="price-table price-table--compact crm-table">
                  <thead>
                    <tr>
                      <th>Дата</th>
                      <th>Что</th>
                      <th className="num">Кг</th>
                      <th className="num">Сумма</th>
                      <th className="num">Доставка + каршеринг</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {report.expenses.rows.map((row) => (
                      <tr key={row.row}>
                        <td className="nowrap">{dateRu(row.expense_date)}</td>
                        <td>{row.item_name}</td>
                        <td className="num">{row.weight_kg || '—'}</td>
                        <td className="num">{money(row.goods_total)}</td>
                        <td className="num">{money(row.delivery_cost + row.carsharing_cost)}</td>
                        <td>{row.duplicate ? <span className="tag">уже в CRM</span> : null}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}

          {report.warnings.length ? (
            <details className="chat-details" open>
              <summary>На что обратить внимание ({report.warnings.length})</summary>
              <ul className="chat-trace">
                {report.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </details>
          ) : null}

          <details className="chat-details">
            <summary>Первые заказы из файла</summary>
            <div className="table-wrap">
              <table className="price-table price-table--compact crm-table">
                <thead>
                  <tr>
                    <th>Стр.</th>
                    <th>Дата</th>
                    <th>Клиент</th>
                    <th>Позиции</th>
                    <th className="num">Сумма</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {report.sample.map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      <td className="nowrap">{dateRu(row.date)}</td>
                      <td>{row.customer}</td>
                      <td>{row.items}</td>
                      <td className="num">
                        {row.approx ? '≈ ' : ''}
                        {money(row.total)}
                      </td>
                      <td>{row.duplicate ? <span className="tag">уже в CRM</span> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          {imported === null ? (
            <div>
              <button
                type="button"
                className="ios-button primary"
                disabled={busy || !isAdmin || !(report.to_import || report.expenses?.new || report.economics?.oils?.length)}
                onClick={() => send(true)}
              >
                {busy
                  ? 'Загружаю…'
                  : `Загрузить: заказов ${report.to_import}, закупок ${report.expenses?.new || 0}, норм ${report.economics?.oils?.length || 0}`}
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
