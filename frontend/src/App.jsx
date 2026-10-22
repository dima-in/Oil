import { useEffect, useState } from 'react'
import { BrowserRouter as Router, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AdminPanel from './components/AdminPanel'
import AssistantDrawer from './components/assistant/AssistantDrawer'
import { AssistantProvider } from './components/assistant/AssistantContext'
import AssistantPage from './components/assistant/AssistantPage'
import Catalog from './components/Catalog'
import CustomerCard from './components/CustomerCard'
import CustomersView from './components/CustomersView'
import Dashboard from './components/Dashboard'
import Icon from './components/Icon'
import Login from './components/Login'
import OrdersView from './components/OrdersView'
import ProductionView from './components/ProductionView'
import QuickOrder from './components/QuickOrder'
import TasksView from './components/TasksView'
import { api } from './lib/api'
import { AUTH_EVENT, clearSession, getStoredUser, getToken, saveSession } from './lib/auth'
import { NAV_SECTIONS } from './lib/constants'
import './index.css'
import './crm.css'

function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute('data-theme') || 'light',
  )
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    try {
      localStorage.setItem('oilpress-theme', next)
    } catch {
      /* private mode: keep the in-memory choice */
    }
  }
  const label = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'
  return (
    <button type="button" className="theme-toggle" onClick={toggle} title={label} aria-label={label}>
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}

function isActive(pathname, path) {
  return path === '/' ? pathname === '/' : pathname === path || pathname.startsWith(`${path}/`)
}

function Sidebar({ user, open, onNavigate }) {
  const location = useLocation()

  return (
    <aside className={open ? 'sidebar sidebar--open' : 'sidebar'}>
      <Link to="/" className="sidebar__brand" onClick={onNavigate}>
        <span className="sidebar__logo">O</span>
        <span>
          OilPress
          <span className="sidebar__tagline">CRM производства</span>
        </span>
      </Link>

      <nav className="sidebar__nav">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title} className="sidebar__section">
            <div className="sidebar__section-title">{section.title}</div>
            {section.items.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={onNavigate}
                className={isActive(location.pathname, item.path) ? 'side-link side-link--active' : 'side-link'}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </Link>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="sidebar__user">
          <div className="sidebar__avatar">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</div>
          <div className="sidebar__user-text">
            <div className="sidebar__user-name">{user.full_name || user.username}</div>
            <div className="sidebar__user-role">{user.role === 'admin' ? 'администратор' : 'менеджер'}</div>
          </div>
        </div>
        <div className="sidebar__footer-actions">
          <ThemeToggle />
          <button type="button" className="theme-toggle" title="Выйти" aria-label="Выйти" onClick={clearSession}>
            <Icon name="logout" />
          </button>
        </div>
      </div>
    </aside>
  )
}

function Shell({ user }) {
  // Меню на телефоне закрывается кликом по пункту (onNavigate) или по затемнению.
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="crm-shell">
      <Sidebar user={user} open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen ? <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} /> : null}

      <div className="crm-main">
        <header className="mobile-bar">
          <button type="button" className="theme-toggle" aria-label="Меню" onClick={() => setMenuOpen(true)}>
            <Icon name="menu" />
          </button>
          <Link to="/" className="mobile-bar__brand">
            OilPress
          </Link>
          <ThemeToggle />
        </header>

        <main className="crm-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/assistant" element={<AssistantPage />} />
            <Route path="/orders" element={<OrdersView />} />
            <Route path="/quick-order" element={<QuickOrder />} />
            <Route path="/customers" element={<CustomersView />} />
            <Route path="/customers/:id" element={<CustomerCard />} />
            <Route path="/tasks" element={<TasksView />} />
            <Route path="/production" element={<ProductionView />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="/admin" element={<AdminPanel user={user} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>

      <AssistantDrawer />
    </div>
  )
}

function useSession() {
  const [user, setUser] = useState(() => (getToken() ? getStoredUser() : null))

  useEffect(() => {
    const sync = () => setUser(getToken() ? getStoredUser() : null)
    window.addEventListener(AUTH_EVENT, sync)
    return () => window.removeEventListener(AUTH_EVENT, sync)
  }, [])

  // Освежаем профиль (роль могли сменить); 401 сам выкинет на экран входа.
  useEffect(() => {
    const token = getToken()
    if (!token) return
    api
      .me()
      .then((fresh) => saveSession(token, fresh))
      .catch(() => {})
  }, [])

  return user
}

export default function App() {
  const user = useSession()

  return (
    <Router>
      {user ? (
        <AssistantProvider>
          <Shell user={user} />
        </AssistantProvider>
      ) : (
        <Login />
      )}
    </Router>
  )
}
