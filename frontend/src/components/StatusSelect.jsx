import { useState } from 'react'
import { api } from '../lib/api'
import { statusTone, useStatuses } from '../lib/statuses'

// Смена статуса прямо в списке: сервер пишет историю, вызывающий получает обновлённый заказ.
export default function StatusSelect({ orderId, status, onChanged, compact = false }) {
  const statuses = useStatuses()
  const [saving, setSaving] = useState(false)
  const current = statuses.find((item) => String(item.id) === String(status))

  const handleChange = async (event) => {
    const next = event.target.value
    if (String(next) === String(status)) return
    setSaving(true)
    try {
      const updated = await api.crm.updateOrder(orderId, { status: Number(next) })
      onChanged?.(updated)
    } catch (error) {
      alert(`Не удалось сменить статус: ${error.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <select
      value={String(status)}
      onChange={handleChange}
      disabled={saving || !statuses.length}
      className={`status-select status-select--${statusTone(current?.role)}${compact ? ' status-select--compact' : ''}`}
      aria-label="Статус заказа"
    >
      {!current ? <option value={String(status)}>{String(status)}</option> : null}
      {statuses.map((item) => (
        <option key={item.id} value={String(item.id)}>
          {item.name}
        </option>
      ))}
    </select>
  )
}
