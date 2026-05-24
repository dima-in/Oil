import { useEffect, useMemo, useState } from 'react'
import PageHeader from './PageHeader'
import { api } from '../lib/api'

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

function createEmptyLine(defaultOilName = '', defaultVolume = '') {
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    oilName: defaultOilName,
    volume: defaultVolume,
    quantity: 1,
  }
}

function toDateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseDateKey(value) {
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

function monthTitle(date) {
  return date.toLocaleDateString('ru-RU', {
    month: 'long',
    year: 'numeric',
  })
}

function buildCalendarDays(monthDate) {
  const firstDay = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
  const firstWeekday = (firstDay.getDay() + 6) % 7
  const start = new Date(firstDay)
  start.setDate(firstDay.getDate() - firstWeekday)

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    return {
      date,
      key: toDateKey(date),
      isCurrentMonth: date.getMonth() === monthDate.getMonth(),
      isToday: toDateKey(date) === toDateKey(new Date()),
    }
  })
}

function normalizeCatalog(items) {
  const grouped = items.reduce((accumulator, item) => {
    if (!accumulator[item.oil_name]) {
      accumulator[item.oil_name] = []
    }

    accumulator[item.oil_name].push({
      oilName: item.oil_name,
      volume: Number(item.volume),
      price: Number(item.price),
    })

    return accumulator
  }, {})

  return Object.entries(grouped)
    .sort(([left], [right]) => left.localeCompare(right, 'ru'))
    .map(([oilName, variants]) => ({
      oilName,
      variants: variants.sort((left, right) => left.volume - right.volume),
    }))
}

function getDefaultLine(groups) {
  const firstGroup = groups[0]
  const firstVariant = firstGroup?.variants?.[0]
  return createEmptyLine(firstGroup?.oilName || '', firstVariant?.volume || '')
}

function getVariant(groups, oilName, volume) {
  return groups
    .find((group) => group.oilName === oilName)
    ?.variants.find((variant) => Number(variant.volume) === Number(volume))
}

function getOrderDateKey(order) {
  if (!order.shipping_date) {
    return null
  }
  return String(order.shipping_date).slice(0, 10)
}

export default function QuickOrder() {
  const todayKey = toDateKey(new Date())
  const [catalogGroups, setCatalogGroups] = useState([])
  const [calendarOrders, setCalendarOrders] = useState({})
  const [selectedDate, setSelectedDate] = useState(todayKey)
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const today = new Date()
    return new Date(today.getFullYear(), today.getMonth(), 1)
  })
  const [form, setForm] = useState({
    name: '',
    phone: '',
    note: '',
  })
  const [lines, setLines] = useState([createEmptyLine()])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function fetchInitialData() {
      try {
        const [catalog, orders] = await Promise.all([
          api.getCatalog(),
          api.getOrders().catch(() => []),
        ])
        if (cancelled) {
          return
        }

        const groups = normalizeCatalog(catalog)
        const ordersByDate = orders.reduce((accumulator, order) => {
          const key = getOrderDateKey(order)
          if (!key) {
            return accumulator
          }
          accumulator[key] = (accumulator[key] || 0) + 1
          return accumulator
        }, {})

        setCatalogGroups(groups)
        setCalendarOrders(ordersByDate)
        if (groups.length > 0) {
          setLines([getDefaultLine(groups)])
        } else {
          setNotice({
            type: 'error',
            text: 'Прайс-лист пустой. Загрузите PDF, CSV или XLSX в админке, затем вернитесь к заказу.',
          })
        }
      } catch (error) {
        if (!cancelled) {
          setNotice({ type: 'error', text: error.message })
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchInitialData()

    return () => {
      cancelled = true
    }
  }, [])

  const calendarDays = useMemo(() => buildCalendarDays(visibleMonth), [visibleMonth])

  const selectedDateLabel = useMemo(() => {
    return parseDateKey(selectedDate).toLocaleDateString('ru-RU', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    })
  }, [selectedDate])

  const items = useMemo(() => {
    return lines
      .map((line) => {
        const variant = getVariant(catalogGroups, line.oilName, line.volume)
        if (!variant || !line.oilName || !line.volume || line.quantity <= 0) {
          return null
        }

        return {
          oil_name: line.oilName,
          volume: Number(line.volume),
          count: Number(line.quantity),
          price: Number(variant.price),
        }
      })
      .filter(Boolean)
  }, [catalogGroups, lines])

  const totalPrice = useMemo(
    () => items.reduce((sum, item) => sum + item.price * item.count, 0),
    [items],
  )

  const totalCount = useMemo(
    () => items.reduce((sum, item) => sum + item.count, 0),
    [items],
  )

  const isValid = catalogGroups.length > 0 && form.name.trim() && items.length > 0

  const updateLine = (lineId, patch) => {
    setLines((previous) =>
      previous.map((line) => {
        if (line.id !== lineId) {
          return line
        }

        const next = { ...line, ...patch }
        if (patch.oilName) {
          const nextGroup = catalogGroups.find((group) => group.oilName === patch.oilName)
          const volumeExists = nextGroup?.variants.some(
            (variant) => Number(variant.volume) === Number(next.volume),
          )
          if (!volumeExists) {
            next.volume = nextGroup?.variants?.[0]?.volume || ''
          }
        }

        return next
      }),
    )
  }

  const addLine = () => {
    if (catalogGroups.length === 0) {
      return
    }

    const firstGroup = catalogGroups[0]
    setLines((previous) => [
      ...previous,
      createEmptyLine(firstGroup.oilName, firstGroup.variants[0]?.volume || ''),
    ])
  }

  const removeLine = (lineId) => {
    setLines((previous) => {
      if (previous.length === 1) {
        return previous
      }
      return previous.filter((line) => line.id !== lineId)
    })
  }

  const changeMonth = (step) => {
    setVisibleMonth((previous) => new Date(previous.getFullYear(), previous.getMonth() + step, 1))
  }

  const selectDate = (dateKey) => {
    setSelectedDate(dateKey)
    setNotice(null)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    if (!isValid) {
      return
    }

    setSubmitting(true)
    setNotice(null)

    try {
      const response = await api.createOrder({
        name: form.name.trim(),
        phone: form.phone.trim(),
        note: form.note.trim(),
        shipping_date: selectedDate,
        items,
      })

      setForm({
        name: '',
        phone: '',
        note: '',
      })
      setLines([getDefaultLine(catalogGroups)])
      setCalendarOrders((previous) => ({
        ...previous,
        [selectedDate]: (previous[selectedDate] || 0) + 1,
      }))
      setNotice({
        type: 'success',
        text: `Заказ #${response.order_id} создан на ${selectedDateLabel}`,
      })
    } catch (error) {
      setNotice({
        type: 'error',
        text: error.message,
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <div className="state-panel">Загрузка формы быстрого заказа...</div>
  }

  return (
    <form className="page-stack quick-order-page" onSubmit={handleSubmit}>
      <PageHeader
        eyebrow="Быстрая запись"
        title="Календарь заказов"
        description="Выберите день в календаре и сразу внесите заказ. Интерфейс рассчитан на работу с телефона."
      />

      {notice ? (
        <div className={notice.type === 'error' ? 'notice notice--error' : 'notice notice--success'}>
          {notice.text}
        </div>
      ) : null}

      <section className="section-card quick-calendar">
        <div className="quick-calendar__top">
          <button type="button" className="quick-calendar__nav" onClick={() => changeMonth(-1)}>
            Назад
          </button>
          <div>
            <h2 className="quick-calendar__title">{monthTitle(visibleMonth)}</h2>
            <p className="quick-calendar__selected">Выбрано: {selectedDateLabel}</p>
          </div>
          <button type="button" className="quick-calendar__nav" onClick={() => changeMonth(1)}>
            Вперед
          </button>
        </div>

        <div className="quick-calendar__weekdays">
          {WEEKDAYS.map((weekday) => (
            <span key={weekday}>{weekday}</span>
          ))}
        </div>

        <div className="quick-calendar__grid">
          {calendarDays.map((day) => {
            const orderCount = calendarOrders[day.key] || 0
            const className = [
              'quick-calendar__day',
              day.isCurrentMonth ? '' : 'quick-calendar__day--muted',
              day.isToday ? 'quick-calendar__day--today' : '',
              day.key === selectedDate ? 'quick-calendar__day--selected' : '',
            ]
              .filter(Boolean)
              .join(' ')

            return (
              <button
                type="button"
                key={day.key}
                className={className}
                onClick={() => selectDate(day.key)}
              >
                <span className="quick-calendar__date">{day.date.getDate()}</span>
                {orderCount > 0 ? (
                  <span className="quick-calendar__badge">{orderCount}</span>
                ) : null}
              </button>
            )
          })}
        </div>
      </section>

      <section className="section-card quick-order-section">
        <div className="section-head">
          <div>
            <h2 className="section-head__title">Клиент</h2>
            <p className="section-head__text">
              Заказ будет записан на {selectedDateLabel}. Имя обязательно, телефон можно оставить пустым.
            </p>
          </div>
        </div>

        <div className="quick-order-form">
          <input
            type="text"
            className="ios-input quick-order-input"
            placeholder="Имя клиента"
            value={form.name}
            onChange={(event) => setForm((previous) => ({ ...previous, name: event.target.value }))}
            required
          />
          <input
            type="tel"
            inputMode="tel"
            className="ios-input quick-order-input"
            placeholder="Телефон, если указан"
            value={form.phone}
            onChange={(event) => setForm((previous) => ({ ...previous, phone: event.target.value }))}
          />
          <textarea
            className="ios-input quick-order-textarea"
            placeholder="Примечание"
            value={form.note}
            onChange={(event) => setForm((previous) => ({ ...previous, note: event.target.value }))}
            rows={3}
          />
        </div>
      </section>

      <section className="section-card quick-order-section">
        <div className="section-head">
          <div>
            <h2 className="section-head__title">Масла</h2>
            <p className="section-head__text">Добавляйте позиции строками: масло, объем и количество.</p>
          </div>
          <button type="button" onClick={addLine} className="ios-button">
            + Добавить масло
          </button>
        </div>

        <div className="quick-order-lines">
          {lines.map((line, index) => {
            const variants =
              catalogGroups.find((group) => group.oilName === line.oilName)?.variants || []
            const selectedVariant = getVariant(catalogGroups, line.oilName, line.volume)

            return (
              <div key={line.id} className="quick-order-line">
                <div className="quick-order-line__index">{index + 1}</div>

                <div className="quick-order-line__fields">
                  <select
                    className="ios-input"
                    value={line.oilName}
                    onChange={(event) => updateLine(line.id, { oilName: event.target.value })}
                    disabled={catalogGroups.length === 0}
                  >
                    {catalogGroups.length === 0 ? (
                      <option value="">Нет позиций в прайсе</option>
                    ) : null}
                    {catalogGroups.map((group) => (
                      <option key={group.oilName} value={group.oilName}>
                        {group.oilName}
                      </option>
                    ))}
                  </select>

                  <select
                    className="ios-input"
                    value={line.volume}
                    onChange={(event) => updateLine(line.id, { volume: Number(event.target.value) })}
                    disabled={variants.length === 0}
                  >
                    {variants.length === 0 ? <option value="">Нет объемов</option> : null}
                    {variants.map((variant) => (
                      <option key={`${line.oilName}_${variant.volume}`} value={variant.volume}>
                        {variant.volume} мл
                      </option>
                    ))}
                  </select>

                  <div className="quick-order-quantity">
                    <button
                      type="button"
                      className="quantity-stepper__button"
                      onClick={() =>
                        updateLine(line.id, { quantity: Math.max(1, Number(line.quantity) - 1) })
                      }
                    >
                      -
                    </button>
                    <input
                      type="number"
                      min="1"
                      className="ios-input quick-order-quantity__input"
                      value={line.quantity}
                      onChange={(event) =>
                        updateLine(line.id, {
                          quantity: Math.max(1, Number(event.target.value) || 1),
                        })
                      }
                    />
                    <button
                      type="button"
                      className="quantity-stepper__button quantity-stepper__button--primary"
                      onClick={() => updateLine(line.id, { quantity: Number(line.quantity) + 1 })}
                    >
                      +
                    </button>
                  </div>
                </div>

                <div className="quick-order-line__summary">
                  <div className="quick-order-line__price">
                    {selectedVariant ? `${selectedVariant.price.toLocaleString('ru-RU')} ₽` : '0 ₽'}
                  </div>
                  <button
                    type="button"
                    className="link-danger"
                    onClick={() => removeLine(line.id)}
                    disabled={lines.length === 1}
                  >
                    Удалить
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <div className="quick-order-submit-bar">
        <div className="app-shell quick-order-submit-bar__inner">
          <div>
            <div className="cart-bar__label">
              {selectedDateLabel}: {items.length} поз., {totalCount} бут.
            </div>
            <div className="cart-bar__total">{totalPrice.toLocaleString('ru-RU')} ₽</div>
          </div>
          <button type="submit" className="ios-button success quick-order-submit-button" disabled={!isValid || submitting}>
            {submitting ? 'Создание...' : 'Создать заказ'}
          </button>
        </div>
      </div>

      <div className="cart-bar__spacer" aria-hidden="true" />
    </form>
  )
}
