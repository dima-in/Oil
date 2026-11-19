import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import CartPanel from './CartPanel'
import Home from './Home'
import Menu from './Menu'
import ProductPage from './ProductPage'
import { shopApi } from './shopApi'
import { phoneDigits, productTitle } from './format'
import useCart, { lineKey } from './useCart'

function CartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 6h15l-1.5 9h-12zM6 6 5 3H2M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM18 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" />
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 9.5c2.6 2 4.6 4 7 6.5 2.3-2.6 4.4-4.6 7-6.8" />
    </svg>
  )
}

function ScrollToTop() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname, hash])
  return null
}

export default function ShopApp() {
  const [info, setInfo] = useState(null)
  const [products, setProducts] = useState(null)
  const [reviews, setReviews] = useState([])
  const [error, setError] = useState(null)
  const [cartOpen, setCartOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [toast, setToast] = useState(null)
  const menuButtonRef = useRef(null)
  const cart = useCart()
  const { add } = cart

  useEffect(() => {
    shopApi.info().then(setInfo).catch(() => {})
    shopApi.catalog().then(setProducts).catch((requestError) => setError(requestError.message))
    shopApi.reviews().then(setReviews).catch(() => {})
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => setToast(null), 2200)
    return () => clearTimeout(timer)
  }, [toast])

  const index = useMemo(() => {
    const map = {}
    ;(products || []).forEach((product) =>
      product.variants.forEach((variant) => {
        map[lineKey({ oil_name: product.name, volume: variant.volume })] = { price: variant.price, title: product.title }
      }),
    )
    return map
  }, [products])

  // Пока каталог грузится, цену не знаем — строки не помечаем «нет в продаже».
  const priced = cart.lines.map((line) => {
    const known = index[lineKey(line)]
    return {
      ...line,
      title: known?.title || productTitle(line.oil_name),
      price: products ? (known ? known.price : null) : 0,
    }
  })
  const cartCount = cart.lines.reduce((sum, line) => sum + line.count, 0)
  const inCartCount = useCallback(
    (name) => cart.lines.filter((line) => line.oil_name === name).reduce((sum, line) => sum + line.count, 0),
    [cart.lines],
  )
  const addToCart = useCallback(
    (name, volume, count) => {
      add(name, volume, count)
      setToast('Добавлено в корзину')
    },
    [add],
  )
  const closeCart = useCallback(() => setCartOpen(false), [])
  const closeMenu = useCallback(() => {
    setMenuOpen(false)
    menuButtonRef.current?.focus({ preventScroll: true })
  }, [])

  const shopName = info?.shop_name || 'Выжимальня'

  return (
    <div className="shop">
      <ScrollToTop />
      <header className="topbar">
        <div className="container topbar__inner">
          <Link to="/" className="brand brand--home" aria-label={`${shopName} — на главную`}>
            <img src="/static/images/brand/logo.png" alt="" className="brand__logo" />
            <span className="brand__name">{shopName}</span>
          </Link>
          {/* На телефоне разделы не помещаются в шапку — логотип открывает меню. */}
          <button ref={menuButtonRef} type="button" className="brand brand--menu" onClick={() => setMenuOpen(true)}
            aria-label="Меню" aria-expanded={menuOpen} aria-controls="site-menu">
            <img src="/static/images/brand/logo.png" alt="" className="brand__logo" />
            <span className="brand__name">{shopName}</span>
            <ChevronIcon />
          </button>
          <nav className="topbar__nav" aria-label="Разделы">
            <Link to="/#catalog">Масла</Link>
            <Link to="/#about">Мастерская</Link>
            <Link to="/#reviews">Отзывы</Link>
            <Link to="/#delivery">Доставка</Link>
          </nav>
          <button type="button" className="cart-button" onClick={() => setCartOpen(true)}
            aria-label={`Корзина, товаров: ${cartCount}`}>
            <CartIcon />
            <span className="cart-button__label">Корзина</span>
            {cartCount ? <span className="cart-button__count">{cartCount}</span> : null}
          </button>
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Home info={info} products={products} reviews={reviews} error={error}
            inCartCount={inCartCount} onAdd={addToCart} />} />
          <Route path="/p/:slug" element={<ProductPage info={info} products={products} inCartCount={inCartCount}
            onAdd={addToCart} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="container footer__inner">
          <div className="footer__brand">
            <img src="/static/images/brand/logo.png" alt="" className="footer__logo" />
            <div>
              <strong>{shopName}</strong>
              <span>сыродавленные масла холодного отжима</span>
            </div>
          </div>
          <div className="footer__links">
            {info?.pickup_address ? <span>{info.pickup_address}</span> : null}
            {info?.phone ? <a href={`tel:${phoneDigits(info.phone)}`}>{info.phone}</a> : null}
            {info?.avito_profile_url ? (
              <a href={info.avito_profile_url} target="_blank" rel="noopener noreferrer">Мы на Авито ↗</a>
            ) : null}
          </div>
        </div>
      </footer>

      {cartCount && !cartOpen ? (
        <button type="button" className="cart-fab" onClick={() => setCartOpen(true)}>
          <CartIcon /> Корзина · {cartCount}
        </button>
      ) : null}

      {toast ? <div className="toast" role="status">{toast}</div> : null}

      <Menu open={menuOpen} onClose={closeMenu} info={info} products={products} shopName={shopName} />
      <CartPanel open={cartOpen} onClose={closeCart} cart={cart} priced={priced} info={info} />
    </div>
  )
}
