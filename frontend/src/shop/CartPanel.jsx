import { useEffect, useRef, useState } from 'react'
import { shopApi } from './shopApi'
import { money, phoneDigits, shortDate, volumeLabel } from './format'
import { metrika } from './metrika'
import { lineKey } from './useCart'

const ADDRESS_HINTS = {
  courier: 'Улица, дом, квартира, подъезд',
  cdek: 'Город и адрес пункта СДЭК или ваш адрес',
  post: 'Индекс, город, улица, дом, квартира',
}

const DELIVERY_NOTES = {
  pickup: (info) => (info?.pickup_address ? `${info.pickup_address}, бесплатно` : 'Адрес и время скажем, когда подтвердим заказ'),
  courier: () => 'По Москве. Стоимость назовём при подтверждении',
  cdek: () => 'До пункта выдачи или курьером СДЭК',
  post: () => 'В любой город России',
}

const EMPTY_FORM = { name: '', phone: '', email: '', method: 'pickup', address: '', comment: '', consent: false, website: '' }

export default function CartPanel({ open, onClose, cart, priced, info }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)
  const [done, setDone] = useState(null)
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.classList.add('no-scroll')
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('no-scroll')
    }
  }, [open, onClose])

  const methods = info?.delivery_methods || []
  const needsAddress = methods.find((method) => method.id === form.method)?.needs_address
  const available = priced.filter((line) => line.price !== null)
  const total = available.reduce((sum, line) => sum + line.price * line.count, 0)
  const set = (field) => (event) =>
    setForm((prev) => ({ ...prev, [field]: event.target.type === 'checkbox' ? event.target.checked : event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    if (!available.length) return setError('Корзина пуста')
    if (phoneDigits(form.phone).length < 10) return setError('Укажите телефон — по нему мы подтвердим заказ')
    if (needsAddress && form.address.trim().length < 5) return setError('Укажите адрес доставки')
    if (!form.consent) return setError('Отметьте согласие на обработку данных')
    setSending(true)
    try {
      const result = await shopApi.placeOrder({
        customer: { name: form.name, phone: form.phone, email: form.email },
        delivery: { method: form.method, address: needsAddress ? form.address : '' },
        comment: form.comment,
        items: available.map(({ oil_name, volume, count }) => ({ oil_name, volume, count })),
        consent: form.consent,
        website: form.website,
      })
      setDone(result)
      metrika('reachGoal', 'order')
      cart.clear()
      setForm(EMPTY_FORM)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSending(false)
    }
  }

  const close = () => {
    setDone(null)
    onClose()
  }

  return (
    <div className={open ? 'drawer drawer--open' : 'drawer'} aria-hidden={!open}>
      <div className="drawer__backdrop" onClick={close} />
      <aside className="drawer__panel" role="dialog" aria-modal="true" aria-labelledby="cart-title">
        <header className="drawer__head">
          <h2 id="cart-title">{done ? 'Заказ принят' : 'Корзина'}</h2>
          <button ref={closeRef} type="button" className="icon-button" aria-label="Закрыть" onClick={close}>
            ×
          </button>
        </header>

        {done ? (
          <div className="drawer__body done">
            <div className="done__mark" aria-hidden="true">✓</div>
            <p className="done__title">
              Спасибо! {done.order_id ? `Ваш заказ №${done.order_id} записан.` : 'Ваш заказ записан.'}
            </p>
            <p>
              Мы позвоним, чтобы подтвердить состав, срок и стоимость доставки
              {done.shipping_date ? ` — ориентировочно масло будет готово к ${shortDate(done.shipping_date)}` : ''}.
            </p>
            {info?.phone ? (
              <p>
                Вопросы — по телефону <a href={`tel:${phoneDigits(info.phone)}`}>{info.phone}</a>
              </p>
            ) : null}
            <button type="button" className="btn btn--primary btn--block" onClick={close}>
              Вернуться в магазин
            </button>
          </div>
        ) : !priced.length ? (
          <div className="drawer__body empty">
            <p>В корзине пока пусто.</p>
            <button type="button" className="btn btn--primary" onClick={close}>
              Выбрать масло
            </button>
          </div>
        ) : (
          <form className="drawer__body" onSubmit={submit} noValidate>
            <ul className="cart-lines">
              {priced.map((line) => (
                <li key={lineKey(line)} className="cart-line">
                  <div className="cart-line__info">
                    <div className="cart-line__title">{line.title}</div>
                    <div className="cart-line__meta">
                      {volumeLabel(line.volume)}
                      {line.price !== null ? ` · ${money(line.price)}` : ' · сейчас нет в продаже'}
                    </div>
                  </div>
                  <div className="stepper stepper--small">
                    <button type="button" aria-label="Меньше" onClick={() => cart.setCount(lineKey(line), line.count - 1)}>
                      −
                    </button>
                    <span>{line.count}</span>
                    <button type="button" aria-label="Больше" onClick={() => cart.setCount(lineKey(line), line.count + 1)}>
                      +
                    </button>
                  </div>
                  <div className="cart-line__sum">{line.price !== null ? money(line.price * line.count) : '—'}</div>
                </li>
              ))}
            </ul>

            <fieldset className="form-block">
              <legend>Контакты</legend>
              <label className="field">
                <span>Имя</span>
                <input className="ym-disable-keys" value={form.name} onChange={set('name')} autoComplete="name" required maxLength={100} />
              </label>
              <label className="field">
                <span>Телефон</span>
                <input className="ym-disable-keys" value={form.phone} onChange={set('phone')} type="tel" autoComplete="tel" inputMode="tel"
                  placeholder="+7 900 000-00-00" required maxLength={20} />
              </label>
              <label className="field">
                <span>Email <em>— необязательно</em></span>
                <input className="ym-disable-keys" value={form.email} onChange={set('email')} type="email" autoComplete="email" maxLength={120} />
              </label>
            </fieldset>

            <fieldset className="form-block">
              <legend>Доставка</legend>
              <div className="delivery-options">
                {methods.map((method) => (
                  <label key={method.id} className={form.method === method.id ? 'option option--active' : 'option'}>
                    <input type="radio" name="delivery" value={method.id} checked={form.method === method.id}
                      onChange={set('method')} />
                    <span className="option__title">{method.label}</span>
                    <span className="option__note">{DELIVERY_NOTES[method.id]?.(info)}</span>
                  </label>
                ))}
              </div>
              {info?.avito_profile_url ? (
                <p className="avito-note">
                  Хотите Авито Доставку? Оформите заказ{' '}
                  <a href={info.avito_profile_url} target="_blank" rel="noopener noreferrer">в нашем профиле на Авито ↗</a>
                </p>
              ) : null}
              {needsAddress ? (
                <label className="field">
                  <span>Адрес</span>
                  <textarea className="ym-disable-keys" rows={2} value={form.address} onChange={set('address')} autoComplete="street-address"
                    placeholder={ADDRESS_HINTS[form.method]} maxLength={300} />
                </label>
              ) : null}
              <label className="field">
                <span>Комментарий <em>— необязательно</em></span>
                <textarea className="ym-disable-keys" rows={2} value={form.comment} onChange={set('comment')} maxLength={1000}
                  placeholder="Когда удобно позвонить, пожелания по заказу" />
              </label>
              {/* Скрытое поле-ловушка для ботов: человек его не видит и не заполняет. */}
              <input className="trap" tabIndex={-1} autoComplete="off" aria-hidden="true" name="website"
                value={form.website} onChange={set('website')} />
            </fieldset>

            <label className="consent">
              <input type="checkbox" checked={form.consent} onChange={set('consent')} />
              <span>Даю согласие на обработку персональных данных для оформления и доставки заказа</span>
            </label>

            <div className="drawer__foot">
              <div className="total">
                <span>Итого без доставки</span>
                <strong>{money(total)}</strong>
              </div>
              {error ? <div className="form-error" role="alert">{error}</div> : null}
              <button type="submit" className="btn btn--primary btn--block btn--large" disabled={sending}>
                {sending ? 'Отправляем…' : 'Оформить заказ'}
              </button>
              <p className="hint">Оплата — после звонка: подтвердим наличие, срок и стоимость доставки.</p>
            </div>
          </form>
        )}
      </aside>
    </div>
  )
}
