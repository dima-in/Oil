import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { dateRu } from '../lib/format'

const SHOP_FIELDS = ['shop_phone', 'shop_pickup_address', 'avito_profile_url', 'avito_rating', 'avito_reviews_count']
const FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'published', label: 'На сайте' },
  { id: 'hidden', label: 'Скрытые' },
]
const EMPTY_REVIEW = { author: '', rating: '5', text: '', item_title: '', review_date: '' }

function stars(value) {
  return value ? '★'.repeat(value) + '☆'.repeat(5 - value) : '—'
}

function ShopSettings({ isAdmin }) {
  const [form, setForm] = useState(null)
  const [notice, setNotice] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.crm
      .settings()
      .then((settings) => setForm(Object.fromEntries(SHOP_FIELDS.map((key) => [key, settings[key] ?? '']))))
      .catch((error) => setNotice({ type: 'error', text: error.message }))
  }, [])

  if (!form) return notice ? <div className="notice notice--error">{notice.text}</div> : null

  const set = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setNotice(null)
    try {
      const saved = await api.crm.updateSettings({
        ...form,
        avito_rating: Number(String(form.avito_rating).replace(',', '.')) || 0,
        avito_reviews_count: Number(form.avito_reviews_count) || 0,
      })
      setForm(Object.fromEntries(SHOP_FIELDS.map((key) => [key, saved[key] ?? ''])))
      setNotice({ type: 'success', text: 'Сохранено — на сайте уже новые данные.' })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="page-stack page-stack--compact" onSubmit={save}>
      <div className="section-head">
        <div>
          <h3 className="section-head__title">Витрина магазина</h3>
          <p className="section-head__text">
            Сайт для покупателей: <a href="/shop" target="_blank" rel="noopener noreferrer">открыть витрину ↗</a>.
            Заказы с сайта приходят в «Заказы» со статусом «новый» и задачей перезвонить.
          </p>
        </div>
      </div>
      <div className="settings-grid">
        <label className="field">
          <span className="field__label">Телефон на сайте</span>
          <input className="ios-input" value={form.shop_phone} onChange={set('shop_phone')} disabled={!isAdmin}
            placeholder="+7 900 000-00-00" />
        </label>
        <label className="field">
          <span className="field__label">Адрес самовывоза</span>
          <input className="ios-input" value={form.shop_pickup_address} onChange={set('shop_pickup_address')}
            disabled={!isAdmin} placeholder="Если пусто — скажем при подтверждении" />
        </label>
        <label className="field">
          <span className="field__label">Профиль на Авито</span>
          <input className="ios-input" value={form.avito_profile_url} onChange={set('avito_profile_url')}
            disabled={!isAdmin} placeholder="https://www.avito.ru/brands/…" />
        </label>
        <label className="field">
          <span className="field__label">Рейтинг на Авито</span>
          <input className="ios-input" inputMode="decimal" value={form.avito_rating} onChange={set('avito_rating')}
            disabled={!isAdmin} placeholder="5,0" />
        </label>
        <label className="field">
          <span className="field__label">Отзывов на Авито</span>
          <input className="ios-input" type="number" min="0" value={form.avito_reviews_count}
            onChange={set('avito_reviews_count')} disabled={!isAdmin} />
        </label>
      </div>
      <span className="muted">
        Рейтинг и число отзывов показываются на сайте. Когда подключите API Авито, они будут обновляться сами.
      </span>
      {notice ? <div className={`notice notice--${notice.type}`}>{notice.text}</div> : null}
      {isAdmin ? (
        <div>
          <button type="submit" className="ios-button primary" disabled={saving}>
            {saving ? 'Сохраняю…' : 'Сохранить'}
          </button>
        </div>
      ) : null}
    </form>
  )
}

function AddReviewForm({ onAdded }) {
  const [form, setForm] = useState(EMPTY_REVIEW)
  const [error, setError] = useState(null)
  const set = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    try {
      await api.crm.createReview({ ...form, rating: Number(form.rating) })
      setForm(EMPTY_REVIEW)
      onAdded()
    } catch (requestError) {
      setError(requestError.message)
    }
  }
  return (
    <form className="page-stack page-stack--compact" onSubmit={submit}>
      <div className="settings-grid">
        <label className="field">
          <span className="field__label">Имя</span>
          <input className="ios-input" value={form.author} onChange={set('author')} />
        </label>
        <label className="field">
          <span className="field__label">Оценка</span>
          <select className="ios-input" value={form.rating} onChange={set('rating')}>
            {[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>{stars(value)}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Дата</span>
          <input className="ios-input" type="date" value={form.review_date} onChange={set('review_date')} />
        </label>
        <label className="field">
          <span className="field__label">О каком товаре</span>
          <input className="ios-input" value={form.item_title} onChange={set('item_title')} placeholder="Льняное масло" />
        </label>
      </div>
      <label className="field">
        <span className="field__label">Текст отзыва</span>
        <textarea className="ios-input" rows={3} value={form.text} onChange={set('text')} />
      </label>
      {error ? <div className="notice notice--error">{error}</div> : null}
      <div>
        <button type="submit" className="ios-button secondary">Добавить отзыв</button>
      </div>
    </form>
  )
}

export default function ShopPanel({ isAdmin }) {
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('all')
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(false)

  const load = () =>
    api.crm
      .reviews()
      .then(setData)
      .catch((error) => setNotice({ type: 'error', text: error.message }))

  useEffect(() => {
    load()
  }, [])

  const reviews = useMemo(() => data?.reviews || [], [data])
  const shown = reviews.filter((review) =>
    filter === 'all' ? true : filter === 'published' ? review.is_published : !review.is_published,
  )
  const publishedCount = reviews.filter((review) => review.is_published).length

  const run = async (action, success) => {
    setBusy(true)
    setNotice(null)
    try {
      const result = await action()
      setNotice({ type: 'success', text: success(result) })
      await load()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }

  const importFile = (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    run(
      async () => {
        const parsed = JSON.parse(await file.text())
        return api.crm.importReviews(Array.isArray(parsed) ? parsed : parsed.reviews)
      },
      (result) =>
        `В файле ${result.received}, новых ${result.added}. О масле — ${result.about_oil}: они сразу на сайте, остальные скрыты.`,
    )
  }

  const togglePublished = async (review) => {
    setData((prev) => ({
      ...prev,
      reviews: prev.reviews.map((row) => (row.id === review.id ? { ...row, is_published: !row.is_published } : row)),
    }))
    try {
      await api.crm.updateReview(review.id, { is_published: !review.is_published })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
      load()
    }
  }

  const avito = data?.avito

  return (
    <div className="page-stack">
      <ShopSettings isAdmin={isAdmin} />

      <div className="page-stack page-stack--compact">
        <div className="section-head">
          <div>
            <h3 className="section-head__title">Отзывы на сайте</h3>
            <p className="section-head__text">
              На сайте показываются отзывы с галочкой. Отзывы о масле включаются сами, о жмыхе и других вещах — скрыты,
              пока вы их не отметите.
            </p>
          </div>
        </div>

        {isAdmin ? (
          <div className="filter-row filter-row--start">
            <label className="ios-button secondary">
              Загрузить отзывы из файла
              <input type="file" accept=".json,application/json" hidden onChange={importFile} disabled={busy} />
            </label>
            {avito?.configured ? (
              <button type="button" className="ios-button secondary" disabled={busy}
                onClick={() => run(api.crm.syncReviews, (result) => `Авито: получено ${result.fetched}, новых ${result.added}.`)}>
                {busy ? 'Обновляю…' : 'Обновить с Авито'}
              </button>
            ) : null}
            <button type="button" className="ios-button secondary" onClick={() => setAdding((value) => !value)}>
              {adding ? 'Скрыть форму' : 'Добавить вручную'}
            </button>
          </div>
        ) : null}

        <span className="muted">
          {avito?.configured
            ? `API Авито подключён. ${avito.synced_at ? `Последнее обновление: ${dateRu(avito.synced_at)}` : 'Ещё не обновлялось.'}`
            : 'API Авито не подключён (ключи AVITO_CLIENT_ID / AVITO_CLIENT_SECRET в .env) — отзывы загружаются из файла или вручную.'}
          {avito?.error ? ` Ошибка: ${avito.error}` : ''}
        </span>

        {adding ? <AddReviewForm onAdded={() => { setAdding(false); load() }} /> : null}
        {notice ? <div className={`notice notice--${notice.type}`}>{notice.text}</div> : null}

        <div className="filter-row filter-row--start">
          {FILTERS.map((item) => (
            <button key={item.id} type="button" onClick={() => setFilter(item.id)}
              className={filter === item.id ? 'filter-chip filter-chip--active' : 'filter-chip'}>
              {item.label}
              {item.id === 'all' ? ` · ${reviews.length}` : item.id === 'published' ? ` · ${publishedCount}` : ` · ${reviews.length - publishedCount}`}
            </button>
          ))}
        </div>

        {!data ? (
          <div className="state-panel">Загрузка…</div>
        ) : !shown.length ? (
          <div className="state-panel">Отзывов нет.</div>
        ) : (
          <ul className="review-admin">
            {shown.map((review) => (
              <li key={review.id} className={review.is_published ? 'review-admin__row' : 'review-admin__row review-admin__row--hidden'}>
                <div className="review-admin__head">
                  <span className="review-admin__stars">{stars(review.rating)}</span>
                  <strong>{review.author}</strong>
                  <span className="muted">{review.review_date ? dateRu(review.review_date) : ''}</span>
                  <span className="muted">· {review.source_label}</span>
                </div>
                {review.item_title ? <div className="muted">{review.item_title}</div> : null}
                <p className="review-admin__text">{review.text || <em className="muted">без текста</em>}</p>
                <div className="review-admin__actions">
                  <label className="review-admin__toggle">
                    <input type="checkbox" checked={review.is_published} disabled={!isAdmin}
                      onChange={() => togglePublished(review)} />
                    на сайте
                  </label>
                  {isAdmin && review.source === 'manual' ? (
                    <button type="button" className="link-button"
                      onClick={() => run(() => api.crm.deleteReview(review.id), () => 'Отзыв удалён.')}>
                      Удалить
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
