import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { dateRu, volume } from '../lib/format'
import { useAssistant } from './assistant/AssistantContext'
import PageHeader from './PageHeader'

const HORIZONS = [7, 14, 30]

export default function ProductionView() {
  const [days, setDays] = useState(14)
  const [stock, setStock] = useState(null)
  const [needs, setNeeds] = useState(null)
  const [schedule, setSchedule] = useState(null)
  const [error, setError] = useState('')
  const assistant = useAssistant()

  useEffect(() => {
    let alive = true
    Promise.all([api.crm.stock(), api.crm.productionNeeds(days), api.crm.productionSchedule(days)])
      .then(([stockRows, needRows, plan]) => {
        if (!alive) return
        setStock(stockRows)
        setNeeds(needRows)
        setSchedule(plan)
      })
      .catch((err) => alive && setError(err.message))
    return () => {
      alive = false
    }
  }, [days])

  if (error) return <div className="notice notice--error">{error}</div>
  if (!stock || !needs || !schedule) return <div className="state-panel">Считаю остатки и загрузку прессов…</div>

  const planDays = schedule.days.filter((day) => day.is_work_day || day.used)

  const tracked = stock.filter((row) => row.tracked)
  const demanded = stock.filter((row) => row.reserved_ml > 0 || row.tracked)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Производство"
        title="Остатки и отжим"
        description="Остаток = произведено партиями − отгружено. Резерв — открытые заказы. Партии, расходы и нормы закладки ведутся в «Управление → Аналитика»."
        actions={
          <div className="header-actions">
            <Link to="/admin" className="ios-button secondary">
              Партии и нормы
            </Link>
            <button
              type="button"
              className="ios-button primary"
              onClick={() => assistant.ask(`Составь план отжима на ${days} дней под открытые заказы: что, сколько закладок и в какие дни.`)}
            >
              План от ИИ
            </button>
          </div>
        }
      />

      <section className="section-card crm-block">
        <div className="crm-block__head">
          <h2 className="crm-block__title">
            План прессов
            <span className={`count-pill${schedule.load_percent > 85 ? ' count-pill--danger' : ''}`}>
              загрузка {schedule.load_percent}%
            </span>
          </h2>
          <span className="muted">
            {schedule.settings.presses_count} пресса × {schedule.settings.press_batches_per_day} закладки в день ·
            отстаивание {schedule.settings.settle_days} дн.
          </span>
        </div>

        {schedule.warnings.length ? (
          <div className="notice notice--warning">
            {schedule.warnings.map((warning) => (
              <div key={warning}>{warning}</div>
            ))}
          </div>
        ) : null}

        <div className="press-plan">
          {planDays.map((day) => (
            <div key={day.date} className={day.used ? 'press-day' : 'press-day press-day--free'}>
              <div className="press-day__head">
                <span className="press-day__date">
                  {day.weekday} {dateRu(day.date).slice(0, 5)}
                </span>
                <span className={day.used > day.capacity ? 'press-day__load press-day__load--over' : 'press-day__load'}>
                  {day.capacity ? `${day.used}/${day.capacity}` : 'выходной'}
                </span>
              </div>
              <div className="press-day__presses">
                {day.presses.map((press) => (
                  <div key={press.press} className="press-cell">
                    <div className="press-cell__label">Пресс {press.press}</div>
                    {press.items.length ? (
                      press.items.map((item, index) => (
                        <div key={index} className={item.kind === 'recorded' ? 'press-item press-item--recorded' : 'press-item'}>
                          {item.oil_name} × {item.batches}
                        </div>
                      ))
                    ) : (
                      <div className="press-item press-item--empty">свободен</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {schedule.seed_purchase.length ? (
          <div className="seed-list">
            <span className="muted">Семян под план:</span>
            {schedule.seed_purchase.map((row) => (
              <span key={row.oil_name} className="tag">
                {row.oil_name} — {row.seed_kg.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} кг
              </span>
            ))}
          </div>
        ) : null}
        <p className="page-hint">
          Серым — партии, уже записанные на эти даты; остальное — предложение планировщика под сроки заказов.
          Число прессов и рабочие дни меняются в «Управление → Настройки».
        </p>
      </section>

      <section className="section-card crm-block">
        <div className="crm-block__head">
          <h2 className="crm-block__title">Нужно отжать под заказы</h2>
          <div className="filter-row filter-row--start">
            {HORIZONS.map((value) => (
              <button
                key={value}
                type="button"
                className={days === value ? 'filter-chip filter-chip--active' : 'filter-chip'}
                onClick={() => setDays(value)}
              >
                {value} дн.
              </button>
            ))}
          </div>
        </div>
        {needs.length ? (
          <div className="table-wrap">
            <table className="price-table crm-table">
              <thead>
                <tr>
                  <th>Масло</th>
                  <th className="num">Нужно</th>
                  <th className="num">Есть</th>
                  <th className="num">Не хватает</th>
                  <th className="num">Закладок</th>
                  <th className="num">Семян, кг</th>
                  <th>Ближайшая отгрузка</th>
                  <th>Заказы</th>
                </tr>
              </thead>
              <tbody>
                {needs.map((item) => (
                  <tr key={item.oil_name} className={item.shortage_ml > 0 ? 'row--warning' : ''}>
                    <td>{item.oil_name}</td>
                    <td className="num">{volume(item.needed_ml)}</td>
                    <td className="num">{item.stock_tracked ? volume(item.on_hand_ml) : <span className="muted">не учтено</span>}</td>
                    <td className="num">{item.shortage_ml > 0 ? volume(item.shortage_ml) : '—'}</td>
                    <td className="num">
                      {item.profile_ready ? item.batches_needed || '—' : <span className="muted">нет нормы</span>}
                    </td>
                    <td className="num">
                      {item.seed_kg_needed ? item.seed_kg_needed.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) : '—'}
                    </td>
                    <td className="nowrap">{dateRu(item.earliest_shipping)}</td>
                    <td>
                      <div className="tag-list">
                        {item.order_ids.map((orderId) => (
                          <Link key={orderId} to={`/orders?focus=${orderId}`} className="tag tag--link">
                            №{orderId}
                          </Link>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="crm-empty">Открытых заказов на этот срок нет.</div>
        )}
      </section>

      <section className="section-card crm-block">
        <div className="crm-block__head">
          <h2 className="crm-block__title">Остатки готового масла</h2>
          <span className="muted">с учётом партий: {tracked.length} из {stock.length}</span>
        </div>
        <div className="table-wrap">
          <table className="price-table crm-table">
            <thead>
              <tr>
                <th>Масло</th>
                <th className="num">Произведено</th>
                <th className="num">Отгружено</th>
                <th className="num">Остаток</th>
                <th className="num">В резерве</th>
                <th className="num">Свободно</th>
                <th>Последняя партия</th>
              </tr>
            </thead>
            <tbody>
              {(demanded.length ? demanded : stock).map((row) => (
                <tr key={row.oil_name} className={row.tracked && row.free_ml < 0 ? 'row--warning' : ''}>
                  <td>{row.oil_name}</td>
                  <td className="num">{row.tracked ? volume(row.produced_ml) : <span className="muted">нет партий</span>}</td>
                  <td className="num">{volume(row.shipped_ml)}</td>
                  <td className="num">{row.tracked ? volume(row.on_hand_ml) : '—'}</td>
                  <td className="num">{row.reserved_ml ? volume(row.reserved_ml) : '—'}</td>
                  <td className="num">{row.tracked ? volume(row.free_ml) : '—'}</td>
                  <td className="nowrap">{row.last_batch_date ? dateRu(row.last_batch_date) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
