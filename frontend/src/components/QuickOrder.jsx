import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { addDaysIso, money, todayIso } from '../lib/format'
import { useDictation } from '../lib/speech'
import Icon from './Icon'
import OrderRow from './OrderRow'
import PageHeader from './PageHeader'

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const STRIP_DAYS = 14
const EMPTY_CUSTOMER = { id: null, name: '', surname: '', phone: '', address: '' }

function parseIso(iso) {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function dayLabel(iso, options = { weekday: 'short', day: 'numeric', month: 'long' }) {
  const today = todayIso()
  if (iso === today) return 'сегодня'
  if (iso === addDaysIso(today, 1)) return 'завтра'
  return parseIso(iso).toLocaleDateString('ru-RU', options)
}

function monthDays(monthIso) {
  const first = parseIso(`${monthIso.slice(0, 7)}-01`)
  const shift = (first.getDay() + 6) % 7
  const start = new Date(first)
  start.setDate(first.getDate() - shift)
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    const iso = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    return { iso, day: date.getDate(), inMonth: date.getMonth() === first.getMonth() }
  })
}

function groupCatalog(items) {
  const groups = {}
  items.forEach((item) => {
    const list = groups[item.oil_name] || (groups[item.oil_name] = [])
    // В прайсе бывают дубли «масло + объём» — показываем вариант один раз.
    if (!list.some((variant) => variant.volume === Number(item.volume))) {
      list.push({ volume: Number(item.volume), price: Number(item.price) })
    }
  })
  return Object.entries(groups)
    .map(([name, variants]) => ({ name, variants: variants.sort((a, b) => a.volume - b.volume) }))
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
}

function useCustomerSuggestions(query, enabled) {
  const [result, setResult] = useState({ query: '', rows: [] })
  const text = query.trim()
  const active = enabled && text.length >= 2
  useEffect(() => {
    if (!active) return undefined
    const timer = setTimeout(() => {
      api.crm
        .customers(text)
        .then((rows) => setResult({ query: text, rows: rows.slice(0, 6) }))
        .catch(() => setResult({ query: text, rows: [] }))
    }, 250)
    return () => clearTimeout(timer)
  }, [active, text])
  // Старые подсказки не показываем, пока не пришёл ответ на текущий текст.
  return active && result.query === text ? result.rows : []
}

export default function QuickOrder() {
  const [searchParams] = useSearchParams()
  const [catalog, setCatalog] = useState([])
  const [selectedDate, setSelectedDate] = useState(searchParams.get('date') || todayIso())
  const [monthOpen, setMonthOpen] = useState(false)
  const [monthCursor, setMonthCursor] = useState(todayIso())
  const [ordersByDay, setOrdersByDay] = useState({})
  const [customer, setCustomer] = useState(EMPTY_CUSTOMER)
  const [lines, setLines] = useState([])
  const [note, setNote] = useState('')
  const [productFilter, setProductFilter] = useState('')
  const [openProduct, setOpenProduct] = useState(null)
  const [freeText, setFreeText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [parseInfo, setParseInfo] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const dictationBase = useRef('')
  const dictation = useDictation((finalText, interim) => {
    const base = dictationBase.current
    setFreeText(`${base}${base && !/\s$/.test(base) ? ' ' : ''}${[finalText, interim].filter(Boolean).join(' ')}`)
  })
  const toggleDictation = () => {
    if (dictation.listening) {
      dictation.stop()
    } else {
      dictationBase.current = freeText
      dictation.start()
    }
  }
  // По телефону ищем, когда набрано хотя бы 4 цифры, иначе — по имени.
  const suggestions = useCustomerSuggestions(
    customer.phone.replace(/\D/g, '').length >= 4 ? customer.phone : customer.name,
    !customer.id,
  )

  const loadOrders = useCallback(async () => {
    // Диапазон: лента на две недели + открытый месяц.
    const monthStart = `${monthCursor.slice(0, 7)}-01`
    const from = [todayIso(), monthStart, selectedDate].sort()[0]
    const to = [addDaysIso(todayIso(), STRIP_DAYS), addDaysIso(monthStart, 41), selectedDate].sort().reverse()[0]
    try {
      const rows = await api.crm.orders({ ship_from: from, ship_to: to })
      const map = {}
      rows
        .filter((order) => order.status_role !== 'cancelled')
        .forEach((order) => {
          ;(map[order.shipping_date] || (map[order.shipping_date] = [])).push(order)
        })
      setOrdersByDay(map)
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    }
  }, [monthCursor, selectedDate])

  useEffect(() => {
    api
      .getCatalog()
      .then((rows) => setCatalog(groupCatalog(rows)))
      .catch((error) => setNotice({ type: 'error', text: error.message }))
  }, [])

  useEffect(() => {
    loadOrders()
  }, [loadOrders])

  const stripDays = useMemo(
    () => Array.from({ length: STRIP_DAYS }, (_, index) => addDaysIso(todayIso(), index)),
    [],
  )
  const visibleProducts = useMemo(() => {
    const filter = productFilter.trim().toLowerCase()
    return filter ? catalog.filter((group) => group.name.toLowerCase().includes(filter)) : catalog
  }, [catalog, productFilter])

  const total = lines.reduce((sum, line) => sum + line.price * line.count, 0)
  const bottles = lines.reduce((sum, line) => sum + line.count, 0)
  const canSubmit = (customer.id || customer.name.trim()) && lines.length > 0 && !submitting
  const dayOrders = ordersByDay[selectedDate] || []

  const addVariant = (name, variant) => {
    setLines((previous) => {
      const existing = previous.find((line) => line.oil_name === name && line.volume === variant.volume)
      if (existing) {
        return previous.map((line) => (line === existing ? { ...line, count: line.count + 1 } : line))
      }
      return [...previous, { oil_name: name, volume: variant.volume, price: variant.price, count: 1 }]
    })
  }

  const changeCount = (index, delta) => {
    setLines((previous) =>
      previous
        .map((line, lineIndex) => (lineIndex === index ? { ...line, count: line.count + delta } : line))
        .filter((line) => line.count > 0),
    )
  }

  const pickDate = (iso) => {
    setSelectedDate(iso)
    setNotice(null)
  }

  const resetForm = () => {
    setCustomer(EMPTY_CUSTOMER)
    setLines([])
    setNote('')
    setFreeText('')
    setParseInfo(null)
  }

  const parseFreeText = async () => {
    if (!freeText.trim()) return
    dictation.stop()
    setParsing(true)
    setParseInfo(null)
    try {
      const draft = await api.assistant.parseOrder(freeText)
      if (draft.customer_match) {
        setCustomer({ ...EMPTY_CUSTOMER, id: draft.customer_match.id, name: draft.customer_match.full_name,
          phone: draft.customer_match.phone || '' })
      } else {
        setCustomer({ ...EMPTY_CUSTOMER, ...draft.customer })
      }
      if (draft.items.length) {
        setLines(draft.items.map((item) => ({ oil_name: item.oil_name, volume: item.volume, price: item.price,
          count: item.count })))
      }
      if (draft.shipping_date) setSelectedDate(draft.shipping_date)
      if (draft.note) setNote(draft.note)
      setParseInfo(draft)
    } catch (error) {
      setParseInfo({ warnings: [error.message], customer_candidates: [] })
    } finally {
      setParsing(false)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setNotice(null)
    try {
      const payload = {
        items: lines.map(({ oil_name, volume, count, price }) => ({ oil_name, volume, count, price })),
        shipping_date: selectedDate,
        note: note.trim() || undefined,
      }
      if (customer.id) payload.customer_id = customer.id
      else payload.customer = { name: customer.name.trim(), surname: customer.surname.trim(), phone: customer.phone.trim(),
        address: customer.address.trim() }
      const order = await api.crm.createOrder(payload)
      setNotice({ type: 'success', text: `Заказ №${order.id} на ${money(order.total_price)} записан на ${dayLabel(selectedDate)}`, orderId: order.id })
      resetForm()
      loadOrders()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setSubmitting(false)
    }
  }

  const monthLabel = parseIso(monthCursor).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })

  return (
    <form className="page-stack quick-order-page" onSubmit={handleSubmit}>
      <PageHeader
        eyebrow="Заказы"
        title="Запись заказа"
        description="Выберите день, посмотрите, что на него уже записано, и внесите заказ — текстом, голосом или плитками."
      />

      {notice ? (
        <div className={notice.type === 'error' ? 'notice notice--error' : 'notice notice--success'}>
          {notice.text}
          {notice.orderId ? (
            <>
              {' · '}
              <Link to={`/orders?focus=${notice.orderId}`} className="crm-link">
                открыть
              </Link>
            </>
          ) : null}
        </div>
      ) : null}

      <section className="section-card day-picker">
        <div className="day-strip" role="listbox" aria-label="День отгрузки">
          {stripDays.map((iso) => {
            const count = (ordersByDay[iso] || []).length
            const date = parseIso(iso)
            return (
              <button
                key={iso}
                type="button"
                role="option"
                aria-selected={iso === selectedDate}
                className={`day-chip${iso === selectedDate ? ' day-chip--active' : ''}${date.getDay() === 0 ? ' day-chip--weekend' : ''}`}
                onClick={() => pickDate(iso)}
              >
                <span className="day-chip__weekday">
                  {iso === todayIso() ? 'сегодня' : iso === addDaysIso(todayIso(), 1) ? 'завтра' : WEEKDAYS[(date.getDay() + 6) % 7]}
                </span>
                <span className="day-chip__date">{date.getDate()}</span>
                <span className={count ? 'day-chip__count' : 'day-chip__count day-chip__count--empty'}>
                  {count ? `${count} зак.` : '—'}
                </span>
              </button>
            )
          })}
          <button type="button" className="day-chip day-chip--more" onClick={() => setMonthOpen((value) => !value)}>
            <Icon name="calendar" />
            <span className="day-chip__weekday">{monthOpen ? 'скрыть' : 'месяц'}</span>
          </button>
        </div>

        {monthOpen ? (
          <div className="quick-calendar">
            <div className="quick-calendar__top">
              <button
                type="button"
                className="quick-calendar__nav"
                onClick={() => setMonthCursor(addDaysIso(`${monthCursor.slice(0, 7)}-01`, -1))}
              >
                ←
              </button>
              <h2 className="quick-calendar__title">{monthLabel}</h2>
              <button
                type="button"
                className="quick-calendar__nav"
                onClick={() => setMonthCursor(addDaysIso(`${monthCursor.slice(0, 7)}-01`, 32))}
              >
                →
              </button>
            </div>
            <div className="quick-calendar__weekdays">
              {WEEKDAYS.map((weekday) => (
                <span key={weekday}>{weekday}</span>
              ))}
            </div>
            <div className="quick-calendar__grid">
              {monthDays(monthCursor).map((day) => {
                const count = (ordersByDay[day.iso] || []).length
                const className = [
                  'quick-calendar__day',
                  day.inMonth ? '' : 'quick-calendar__day--muted',
                  day.iso === todayIso() ? 'quick-calendar__day--today' : '',
                  day.iso === selectedDate ? 'quick-calendar__day--selected' : '',
                ]
                  .filter(Boolean)
                  .join(' ')
                return (
                  <button
                    key={day.iso}
                    type="button"
                    className={className}
                    onClick={() => {
                      pickDate(day.iso)
                      setMonthOpen(false)
                    }}
                  >
                    <span className="quick-calendar__date">{day.day}</span>
                    {count ? <span className="quick-calendar__badge">{count}</span> : null}
                  </button>
                )
              })}
            </div>
          </div>
        ) : null}

        <div className="day-agenda">
          <div className="day-agenda__title">
            {dayLabel(selectedDate, { weekday: 'long', day: 'numeric', month: 'long' })}:{' '}
            {dayOrders.length ? `${dayOrders.length} заказ(а)` : 'заказов нет'}
          </div>
          {dayOrders.length ? (
            <div className="crm-list">
              {dayOrders.map((order) => (
                <OrderRow key={order.id} order={order} onChanged={loadOrders} />
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="section-card quick-order-section">
        <div className="section-head">
          <div>
            <h2 className="section-head__title">Новый заказ — {dayLabel(selectedDate)}</h2>
            <p className="section-head__text">
              Опишите заказ как в мессенджере или надиктуйте — форма заполнится сама. Или соберите вручную ниже.
            </p>
          </div>
        </div>

        <div className="free-order">
          <textarea
            className="ios-input free-order__input"
            rows={3}
            value={freeText}
            onChange={(event) => setFreeText(event.target.value)}
            placeholder="Например: Иван, 8 916 123-45-67, две по пол-литра льняного и литр тыквенного, заберёт в пятницу после шести"
          />
          <div className="free-order__buttons">
            <button
              type="button"
              className={`icon-button icon-button--mic${dictation.listening ? ' icon-button--recording' : ''}`}
              title={dictation.supported ? 'Надиктовать заказ' : dictation.reason}
              onClick={toggleDictation}
            >
              <Icon name="mic" />
            </button>
            <button
              type="button"
              className="ios-button primary"
              disabled={parsing || !freeText.trim()}
              onClick={parseFreeText}
            >
              {parsing ? 'Разбираю…' : 'Разобрать'}
            </button>
          </div>
        </div>
        {dictation.error ? <div className="assistant__hint assistant__hint--error">{dictation.error}</div> : null}
        {dictation.listening ? (
          <div className="assistant__hint assistant__hint--live">
            <span className="rec-dot" /> Слушаю… кто, что, сколько, когда. Нажмите микрофон, чтобы закончить.
          </div>
        ) : null}
        {parseInfo?.warnings?.length ? (
          <div className="notice notice--warning">
            {parseInfo.warnings.map((warning) => (
              <div key={warning}>{warning}</div>
            ))}
          </div>
        ) : null}

        <div className="form-block">
          <div className="form-block__title">Клиент</div>
          {customer.id ? (
            <div className="customer-chip">
              <span>
                <strong>{customer.name}</strong> {customer.phone ? `· ${customer.phone}` : ''} — клиент из базы
              </span>
              <button type="button" className="link-button" onClick={() => setCustomer(EMPTY_CUSTOMER)}>
                сменить
              </button>
            </div>
          ) : (
            <>
              <div className="quick-order-form quick-order-form--two">
                <input
                  className="ios-input"
                  placeholder="Имя клиента *"
                  value={customer.name}
                  onChange={(event) => setCustomer((prev) => ({ ...prev, name: event.target.value }))}
                />
                <input
                  className="ios-input"
                  type="tel"
                  inputMode="tel"
                  placeholder="Телефон"
                  value={customer.phone}
                  onChange={(event) => setCustomer((prev) => ({ ...prev, phone: event.target.value }))}
                />
              </div>
              {[...(parseInfo?.customer_candidates || []), ...suggestions]
                .filter((row, index, all) => all.findIndex((other) => other.id === row.id) === index)
                .slice(0, 6).length ? (
                <div className="suggestions">
                  <span className="muted">Уже есть в базе:</span>
                  {[...(parseInfo?.customer_candidates || []), ...suggestions]
                    .filter((row, index, all) => all.findIndex((other) => other.id === row.id) === index)
                    .slice(0, 6)
                    .map((row) => (
                      <button
                        key={row.id}
                        type="button"
                        className="prompt-chip prompt-chip--small"
                        onClick={() => setCustomer({ ...EMPTY_CUSTOMER, id: row.id, name: row.full_name, phone: row.phone || '' })}
                      >
                        {row.full_name}
                        {row.phone ? ` · ${row.phone}` : ''}
                      </button>
                    ))}
                </div>
              ) : null}
            </>
          )}
        </div>

        <div className="form-block">
          <div className="form-block__title">Масла</div>
          <input
            className="ios-input search-input"
            placeholder="Найти масло…"
            value={productFilter}
            onChange={(event) => setProductFilter(event.target.value)}
          />
          <div className="product-chips">
            {visibleProducts.map((group) => (
              <div key={group.name} className={openProduct === group.name ? 'product-chip product-chip--open' : 'product-chip'}>
                <button
                  type="button"
                  className="product-chip__name"
                  onClick={() => setOpenProduct(openProduct === group.name ? null : group.name)}
                >
                  {group.name}
                </button>
                {openProduct === group.name ? (
                  <div className="product-chip__variants">
                    {group.variants.map((variant) => (
                      <button
                        key={variant.volume}
                        type="button"
                        className="variant-button"
                        onClick={() => addVariant(group.name, variant)}
                      >
                        <span>{variant.volume} мл</span>
                        <span className="muted">{money(variant.price)}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
            {!visibleProducts.length ? <span className="muted">Ничего не нашлось</span> : null}
          </div>

          {lines.length ? (
            <div className="order-lines">
              {lines.map((line, index) => (
                <div key={`${line.oil_name}_${line.volume}`} className="order-line">
                  <div className="order-line__name">
                    {line.oil_name}, {line.volume} мл
                    <span className="muted"> · {money(line.price)}</span>
                  </div>
                  <div className="quantity-stepper">
                    <button type="button" className="quantity-stepper__button" onClick={() => changeCount(index, -1)}>
                      −
                    </button>
                    <span className="quantity-stepper__value">{line.count}</span>
                    <button
                      type="button"
                      className="quantity-stepper__button quantity-stepper__button--primary"
                      onClick={() => changeCount(index, 1)}
                    >
                      +
                    </button>
                  </div>
                  <div className="order-line__sum">{money(line.price * line.count)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="crm-empty">Позиций пока нет — нажмите на масло и выберите объём.</div>
          )}
        </div>

        <div className="form-block">
          <div className="form-block__title">Комментарий</div>
          <textarea
            className="ios-input"
            rows={2}
            placeholder="Время, доставка, пожелания"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
      </section>

      <div className="quick-order-submit-bar">
        <div className="quick-order-submit-bar__inner">
          <div>
            <div className="cart-bar__label">
              {dayLabel(selectedDate)} · {lines.length} поз., {bottles} бут.
            </div>
            <div className="cart-bar__total">{money(total)}</div>
          </div>
          <button type="submit" className="ios-button success quick-order-submit-button" disabled={!canSubmit}>
            {submitting ? 'Записываю…' : `Записать на ${dayLabel(selectedDate, { weekday: 'short', day: 'numeric', month: 'short' })}`}
          </button>
        </div>
      </div>
      <div className="cart-bar__spacer" aria-hidden="true" />
    </form>
  )
}
