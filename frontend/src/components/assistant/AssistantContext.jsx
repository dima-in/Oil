/* eslint-disable react-refresh/only-export-components -- провайдер и его хук живут вместе */
import { createContext, useCallback, useContext, useMemo, useState } from 'react'

// Один помощник на всё приложение: панель открывается из любого экрана,
// а экран может сразу задать вопрос (ask), подставить шаблон в поле ввода (prefill)
// и передать контекст (например, карточку клиента).
const AssistantContext = createContext({
  isOpen: false,
  open: () => {},
  close: () => {},
  ask: () => {},
  prefill: () => {},
  request: null,
  consumeRequest: () => {},
})

export function AssistantProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false)
  const [request, setRequest] = useState(null)

  const open = useCallback(() => setIsOpen(true), [])
  const close = useCallback(() => setIsOpen(false), [])
  const ask = useCallback((text, context) => {
    setRequest({ text, context, at: Date.now() })
    setIsOpen(true)
  }, [])
  const prefill = useCallback((text, { listen = false } = {}) => {
    setRequest({ text, prefill: true, listen, at: Date.now() })
    setIsOpen(true)
  }, [])
  const consumeRequest = useCallback(() => setRequest(null), [])

  const value = useMemo(
    () => ({ isOpen, open, close, ask, prefill, request, consumeRequest }),
    [isOpen, open, close, ask, prefill, request, consumeRequest],
  )
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>
}

export function useAssistant() {
  return useContext(AssistantContext)
}
