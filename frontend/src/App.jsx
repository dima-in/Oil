import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Catalog from './components/Catalog'
import OrderCart from './components/OrderCart'
import AdminPanel from './components/AdminPanel'
import OrdersView from './components/OrdersView'
import './index.css'

function Navigation() {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: '🛒 Каталог', icon: '📦' },
    { path: '/orders', label: 'Заказы', icon: '📋' },
    { path: '/admin', label: 'Админ', icon: '⚙️' },
  ]

  return (
    <nav className="ios-nav">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          <Link to="/" className="text-xl font-bold bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent">
            🛢️ OilPress
          </Link>
          
          <div className="flex gap-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  location.pathname === item.path
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-black">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Catalog />} />
            <Route path="/orders" element={<OrdersView />} />
            <Route path="/admin" element={<AdminPanel />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
