import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Icon from '../Icon'
import AssistantChat from './AssistantChat'
import { useAssistant } from './AssistantContext'

// Панель помощника поверх любого экрана. Остаётся смонтированной, когда скрыта:
// закрытие панели посреди ответа не теряет ни ответ, ни черновики действий.
export default function AssistantDrawer() {
  const { isOpen, open, close } = useAssistant()
  const location = useLocation()

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [close])

  if (location.pathname === '/assistant') return null

  return (
    <>
      {!isOpen ? (
        <button type="button" className="assistant-fab" onClick={open} title="ИИ-помощник">
          <Icon name="spark" size={20} />
          <span>Спросить ИИ</span>
        </button>
      ) : null}
      <div className={isOpen ? 'assistant-drawer assistant-drawer--open' : 'assistant-drawer'} aria-hidden={!isOpen}>
        <AssistantChat variant="drawer" />
      </div>
    </>
  )
}
