import { BrowserRouter as Router, Link, Route, Routes, useLocation } from 'react-router-dom'
import AdminPanel from './components/AdminPanel'
import Catalog from './components/Catalog'
import OrdersView from './components/OrdersView'
import { NAV_ITEMS } from './lib/constants'
import './index.css'

function Navigation() {
  const location = useLocation()

  return (
    <nav className="app-nav">
      <div className="app-shell app-nav__inner">
        <div className="app-nav__brand-wrap">
          <Link to="/" className="app-nav__brand">
            OilPress
          </Link>
          <div className="app-nav__meta">Каталог, заказы и прайс-лист</div>
        </div>

        <div className="app-nav__links">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={location.pathname === item.path ? 'nav-link nav-link--active' : 'nav-link'}
            >
              <span className="nav-link__icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.shortLabel}</span>
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}

function AppLayout() {
  return (
    <div className="app-root">
      <Navigation />
      <main className="app-shell app-main">
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/orders" element={<OrdersView />} />
          <Route path="/admin" element={<AdminPanel />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Router>
      <AppLayout />
    </Router>
  )
}
