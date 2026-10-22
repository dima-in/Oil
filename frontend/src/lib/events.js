import { useEffect } from 'react'

// Данные изменились не на этом экране (например, ассистент подтвердил заказ) —
// открытые списки перечитывают себя.
export const DATA_CHANGED_EVENT = 'oilpress:data-changed'

export function notifyDataChanged() {
  window.dispatchEvent(new Event(DATA_CHANGED_EVENT))
}

export function useDataRefresh(callback) {
  useEffect(() => {
    window.addEventListener(DATA_CHANGED_EVENT, callback)
    return () => window.removeEventListener(DATA_CHANGED_EVENT, callback)
  }, [callback])
}
