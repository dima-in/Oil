import { useEffect, useState } from 'react'
import { api } from './api'

// Справочник статусов берём из базы: номера в разных установках разные,
// а роль (new/done/cancelled/awaiting_payment) сервер вычисляет по названию.
let cache = null
let pending = null

export function loadStatuses({ force = false } = {}) {
  if (cache && !force) return Promise.resolve(cache)
  if (!pending) {
    pending = api.crm
      .statuses()
      .then((rows) => {
        cache = rows
        return rows
      })
      .finally(() => {
        pending = null
      })
  }
  return pending
}

export function useStatuses() {
  const [statuses, setStatuses] = useState(cache || [])
  useEffect(() => {
    let alive = true
    loadStatuses()
      .then((rows) => alive && setStatuses(rows))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])
  return statuses
}

const ROLE_TONES = {
  new: 'blue',
  done: 'green',
  cancelled: 'red',
  awaiting_payment: 'amber',
}

export function statusTone(role) {
  return ROLE_TONES[role] || 'slate'
}
