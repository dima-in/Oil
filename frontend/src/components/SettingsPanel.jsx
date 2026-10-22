import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const DAYS = [
  [1, 'Пн'],
  [2, 'Вт'],
  [3, 'Ср'],
  [4, 'Чт'],
  [5, 'Пт'],
  [6, 'Сб'],
  [7, 'Вс'],
]

export default function SettingsPanel({ isAdmin }) {
  const [form, setForm] = useState(null)
  const [notice, setNotice] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.crm
      .settings()
      .then(setForm)
      .catch((error) => setNotice({ type: 'error', text: error.message }))
  }, [])

  if (!form) return notice ? <div className="notice notice--error">{notice.text}</div> : <div className="state-panel">Загрузка…</div>

  const set = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  const toggleDay = (day) =>
    setForm((prev) => {
      const days = new Set(prev.work_days_list)
      if (days.has(day)) days.delete(day)
      else days.add(day)
      return { ...prev, work_days_list: [...days].sort() }
    })

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setNotice(null)
    try {
      const saved = await api.crm.updateSettings({
        company_name: form.company_name,
        business_profile: form.business_profile,
        presses_count: Number(form.presses_count),
        press_batches_per_day: Number(form.press_batches_per_day),
        settle_days: Number(form.settle_days),
        work_days: form.work_days_list,
      })
      setForm(saved)
      setNotice({ type: 'success', text: 'Сохранено. Планировщик и ИИ-помощник уже используют новые настройки.' })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setSaving(false)
    }
  }

  const capacity = Number(form.presses_count || 0) * Number(form.press_batches_per_day || 0)

  return (
    <form className="page-stack page-stack--compact" onSubmit={save}>
      <div className="section-head">
        <div>
          <h3 className="section-head__title">Производство и компания</h3>
          <p className="section-head__text">
            Эти параметры использует планировщик прессов и знает ИИ-помощник, когда обещает сроки.
          </p>
        </div>
      </div>

      <div className="settings-grid">
        <label className="field">
          <span className="field__label">Название</span>
          <input className="ios-input" value={form.company_name} onChange={set('company_name')} disabled={!isAdmin} />
        </label>
        <label className="field">
          <span className="field__label">Прессов</span>
          <input className="ios-input" type="number" min="1" max="20" value={form.presses_count}
            onChange={set('presses_count')} disabled={!isAdmin} />
        </label>
        <label className="field">
          <span className="field__label">Закладок на пресс в день</span>
          <input className="ios-input" type="number" min="1" max="24" value={form.press_batches_per_day}
            onChange={set('press_batches_per_day')} disabled={!isAdmin} />
        </label>
        <label className="field">
          <span className="field__label">Дней отстаивания до отгрузки</span>
          <input className="ios-input" type="number" min="0" max="14" value={form.settle_days}
            onChange={set('settle_days')} disabled={!isAdmin} />
        </label>
      </div>

      <div className="field">
        <span className="field__label">Рабочие дни</span>
        <div className="filter-row filter-row--start">
          {DAYS.map(([day, label]) => (
            <button
              key={day}
              type="button"
              disabled={!isAdmin}
              className={form.work_days_list.includes(day) ? 'filter-chip filter-chip--active' : 'filter-chip'}
              onClick={() => toggleDay(day)}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="muted">Мощность: до {capacity} закладок в рабочий день.</span>
      </div>

      <label className="field">
        <span className="field__label">О бизнесе — для ИИ-помощника</span>
        <textarea className="ios-input" rows={4} value={form.business_profile} onChange={set('business_profile')}
          disabled={!isAdmin} />
        <span className="muted">Чем занимаетесь, каналы продаж, особенности — помощник учтёт это в ответах.</span>
      </label>

      {notice ? <div className={`notice notice--${notice.type}`}>{notice.text}</div> : null}
      {isAdmin ? (
        <div>
          <button type="submit" className="ios-button primary" disabled={saving}>
            {saving ? 'Сохраняю…' : 'Сохранить'}
          </button>
        </div>
      ) : (
        <div className="muted">Менять настройки может администратор.</div>
      )}
    </form>
  )
}
