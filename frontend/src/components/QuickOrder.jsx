import { useEffect, useMemo, useState } from 'react'
import PageHeader from './PageHeader'
import { api } from '../lib/api'

function createEmptyLine(defaultOilName = '', defaultVolume = '') {
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    oilName: defaultOilName,
    volume: defaultVolume,
    quantity: 1,
  }
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

export default function QuickOrder() {
  const [catalogGroups, setCatalogGroups] = useState([])
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

    async function fetchCatalog() {
      try {
        const data = await api.getCatalog()
        if (cancelled) {
          return
        }

        const groups = normalizeCatalog(data)
        setCatalogGroups(groups)
        if (groups.length > 0) {
          setLines([getDefaultLine(groups)])
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

    fetchCatalog()

    return () => {
      cancelled = true
    }
  }, [])

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

  const isValid = form.name.trim() && items.length > 0

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
        items,
      })

      setForm({
        name: '',
        phone: '',
        note: '',
      })
      setLines([getDefaultLine(catalogGroups)])
      setNotice({
        type: 'success',
        text: `Заказ #${response.order_id} создан`,
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
        eyebrow="Быстрое оформление"
        title="Быстрый заказ"
        description="Форма для записи заказа с телефона: минимум полей, быстрый выбор масел и фиксированная кнопка создания."
      />

      {notice ? (
        <div className={notice.type === 'error' ? 'notice notice--error' : 'notice notice--success'}>
          {notice.text}
        </div>
      ) : null}

      <section className="section-card quick-order-section">
        <div className="section-head">
          <div>
            <h2 className="section-head__title">Клиент</h2>
            <p className="section-head__text">Имя обязательно, телефон можно оставить пустым.</p>
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
                  >
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
                  >
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
            <div className="cart-bar__label">Позиций: {items.length}, бутылок: {totalCount}</div>
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
