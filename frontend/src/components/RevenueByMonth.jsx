import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useDataRefresh } from '../lib/events'
import { money } from '../lib/format'

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

function monthLabel(key, withYear = true) {
  const [year, month] = key.split('-').map(Number)
  return withYear ? `${MONTHS[month - 1]} ${String(year).slice(2)}` : MONTHS[month - 1]
}

function compact(value) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн`
  if (value >= 1000) return `${Math.round(value / 1000).toLocaleString('ru-RU')} тыс`
  return String(Math.round(value))
}

// Ровная шкала: шаг 1/2/2,5/5 × 10^k, около четырёх делений.
function niceScale(max) {
  if (max <= 0) return { top: 1, ticks: [0] }
  const rough = max / 4
  const power = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough)
  const top = Math.ceil(max / step) * step
  const ticks = []
  for (let value = 0; value <= top + step / 2; value += step) ticks.push(value)
  return { top, ticks }
}

// Столбцы выручки по месяцам: одна серия, подсказка при наведении, таблица под графиком.
export function MonthlyRevenueChart({ rows, note }) {
  const [active, setActive] = useState(null)
  const { top, ticks } = useMemo(() => niceScale(Math.max(0, ...rows.map((row) => row.revenue))), [rows])
  const peak = useMemo(() => rows.reduce((best, row) => (row.revenue > (best?.revenue ?? -1) ? row : best), null), [rows])
  const last = rows[rows.length - 1]
  const total = rows.reduce((sum, row) => sum + row.revenue, 0)
  const withOrders = rows.filter((row) => row.orders)
  const average = withOrders.length ? total / withOrders.length : 0
  const hovered = active !== null ? rows[active] : null
  // Подписи месяцев не должны налезать друг на друга: при длинном периоде — через одну-две.
  const labelStep = rows.length > 18 ? 3 : rows.length > 12 ? 2 : 1

  if (!rows.length) return <div className="crm-empty">Заказов за этот период нет.</div>

  return (
    <div className="revenue-chart">
      <div className="revenue-chart__summary">
        <div>
          <div className="kpi__label">Всего за период</div>
          <div className="revenue-chart__total">{money(total)}</div>
        </div>
        <div>
          <div className="kpi__label">В среднем за месяц</div>
          <div className="revenue-chart__avg">{money(average)}</div>
        </div>
        {peak?.revenue ? (
          <div>
            <div className="kpi__label">Лучший месяц</div>
            <div className="revenue-chart__avg">
              {monthLabel(peak.month)} · {money(peak.revenue)}
            </div>
          </div>
        ) : null}
      </div>

      <div className="revenue-chart__plot" onMouseLeave={() => setActive(null)}>
        <div className="revenue-chart__grid" aria-hidden="true">
          {ticks.map((tick) => (
            <div key={tick} className="revenue-chart__gridline" style={{ bottom: `${(tick / top) * 100}%` }}>
              <span>{compact(tick)}</span>
            </div>
          ))}
        </div>
        <div className="revenue-chart__bars" role="list" aria-label="Выручка по месяцам">
          {rows.map((row, index) => {
            const height = top ? (row.revenue / top) * 100 : 0
            const labelled = row === peak || row === last
            return (
              <div
                key={row.month}
                role="listitem"
                className={active === index ? 'revenue-bar revenue-bar--active' : 'revenue-bar'}
                onMouseEnter={() => setActive(index)}
                onClick={() => setActive(active === index ? null : index)}
                aria-label={`${monthLabel(row.month)}: ${money(row.revenue)}, заказов ${row.orders}`}
              >
                <div className="revenue-bar__track">
                  {labelled && row.revenue ? (
                    <span className="revenue-bar__value" style={{ bottom: `calc(${height}% + 4px)` }}>
                      {compact(row.revenue)}
                    </span>
                  ) : null}
                  <div className="revenue-bar__fill" style={{ height: `${height}%` }} />
                </div>
                <div className="revenue-bar__label">
                  {index % labelStep === 0 || row.month.endsWith('-01')
                    ? row.month.endsWith('-01') || index === 0
                      ? monthLabel(row.month)
                      : monthLabel(row.month, false)
                    : ''}
                </div>
              </div>
            )
          })}
        </div>
        {hovered ? (
          <div
            className="revenue-chart__tooltip"
            style={{ left: `${((active + 0.5) / rows.length) * 100}%` }}
            role="status"
          >
            <strong>{monthLabel(hovered.month)}</strong>
            <span>{money(hovered.revenue)}</span>
            <span className="muted">
              заказов {hovered.orders}
              {hovered.avg_check ? ` · ср. чек ${money(hovered.avg_check)}` : ''}
            </span>
          </div>
        ) : null}
      </div>

      {note ? <p className="page-hint">{note}</p> : null}

      <details className="chat-details">
        <summary>Таблица по месяцам</summary>
        <div className="table-wrap">
          <table className="price-table price-table--compact crm-table">
            <thead>
              <tr>
                <th>Месяц</th>
                <th className="num">Заказов</th>
                <th className="num">Бутылок</th>
                <th className="num">Выручка</th>
                <th className="num">Средний чек</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.month}>
                  <td>{monthLabel(row.month)}</td>
                  <td className="num">{row.orders}</td>
                  <td className="num">{row.bottles ?? '—'}</td>
                  <td className="num">{money(row.revenue)}</td>
                  <td className="num">{row.orders ? money(row.avg_check ?? row.revenue / row.orders) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

// Блок для «Сегодня»: выручка из CRM по месяцам за 12 или 24 месяца.
export default function RevenueByMonth() {
  const [months, setMonths] = useState(12)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await api.crm.revenueByMonth(months)
      setError('')
      setRows(data)
    } catch (err) {
      setError(err.message)
    }
  }, [months])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии блока
    load()
  }, [load])
  useDataRefresh(load)

  return (
    <section className="section-card crm-block">
      <div className="crm-block__head">
        <div>
          <h2 className="crm-block__title">Выручка по месяцам</h2>
          <div className="muted">по дате заказа, без отменённых</div>
        </div>
        <div className="filter-row filter-row--start">
          {[12, 24].map((value) => (
            <button
              key={value}
              type="button"
              className={months === value ? 'filter-chip filter-chip--active' : 'filter-chip'}
              onClick={() => setMonths(value)}
            >
              {value} мес.
            </button>
          ))}
        </div>
      </div>
      {error ? <div className="notice notice--error">{error}</div> : null}
      {rows ? <MonthlyRevenueChart rows={rows} /> : !error ? <div className="crm-empty">Считаю…</div> : null}
    </section>
  )
}
