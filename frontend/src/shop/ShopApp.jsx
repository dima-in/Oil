import { useCallback, useEffect, useMemo, useState } from 'react'
import CartPanel from './CartPanel'
import ProductCard, { DropIcon } from './ProductCard'
import Reviews, { Stars } from './Reviews'
import { shopApi } from './shopApi'
import { phoneDigits, ratingLabel, reviewsWord } from './format'
import useCart, { lineKey } from './useCart'

const DELIVERY_TEXT = {
  pickup: 'Заберите заказ сами — адрес и время согласуем по телефону.',
  courier: 'Привезём по городу в удобное время.',
  cdek: 'До пункта выдачи СДЭК или курьером до двери.',
  post: 'Отправим в любой город России.',
}

function CartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 6h15l-1.5 9h-12zM6 6 5 3H2M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM18 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" />
    </svg>
  )
}

function SkeletonGrid() {
  return (
    <div className="catalog" aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="product product--skeleton" />
      ))}
    </div>
  )
}

export default function ShopApp() {
  const [info, setInfo] = useState(null)
  const [products, setProducts] = useState(null)
  const [reviews, setReviews] = useState([])
  const [error, setError] = useState(null)
  const [cartOpen, setCartOpen] = useState(false)
  const [toast, setToast] = useState(null)
  const cart = useCart()

  useEffect(() => {
    shopApi.info().then(setInfo).catch(() => {})
    shopApi.catalog().then(setProducts).catch((requestError) => setError(requestError.message))
    shopApi.reviews().then(setReviews).catch(() => {})
  }, [])

  useEffect(() => {
    if (info?.company_name) document.title = `${info.company_name} — масла холодного отжима`
  }, [info])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => setToast(null), 2200)
    return () => clearTimeout(timer)
  }, [toast])

  const prices = useMemo(() => {
    const index = {}
    ;(products || []).forEach((product) =>
      product.variants.forEach((variant) => {
        index[lineKey({ oil_name: product.name, volume: variant.volume })] = variant.price
      }),
    )
    return index
  }, [products])

  // Пока каталог грузится, цену не знаем — строки не помечаем «нет в продаже».
  const priced = cart.lines.map((line) => ({
    ...line,
    price: products ? (prices[lineKey(line)] ?? null) : 0,
  }))
  const cartCount = cart.lines.reduce((sum, line) => sum + line.count, 0)
  const inCartCount = (name) =>
    cart.lines.filter((line) => line.oil_name === name).reduce((sum, line) => sum + line.count, 0)

  const addToCart = useCallback(
    (name, volume, count) => {
      cart.add(name, volume, count)
      setToast('Добавлено в корзину')
    },
    [cart],
  )
  const closeCart = useCallback(() => setCartOpen(false), [])

  const companyName = info?.company_name || 'Маслобойня'
  const gallery = (products || []).filter((product) => product.image).slice(0, 4)
  const rating = info?.avito_rating

  return (
    <div className="shop">
      <header className="topbar">
        <div className="container topbar__inner">
          <a href="#top" className="brand">
            <span className="brand__mark"><DropIcon size={18} /></span>
            {companyName}
          </a>
          <nav className="topbar__nav" aria-label="Разделы">
            <a href="#catalog">Каталог</a>
            {reviews.length || rating ? <a href="#reviews">Отзывы</a> : null}
            <a href="#delivery">Доставка</a>
          </nav>
          <button type="button" className="cart-button" onClick={() => setCartOpen(true)}
            aria-label={`Корзина, товаров: ${cartCount}`}>
            <CartIcon />
            <span className="cart-button__label">Корзина</span>
            {cartCount ? <span className="cart-button__count">{cartCount}</span> : null}
          </button>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="container hero__inner">
            <div className="hero__text">
              <p className="eyebrow">Сыродавленные масла холодного отжима</p>
              <h1>Свежее масло — отжимаем под&nbsp;ваш заказ</h1>
              <p className="hero__lead">
                Давим небольшими партиями на своих прессах, поэтому масло приходит свежим, с живым вкусом и запахом
                семян.
              </p>
              <div className="hero__actions">
                <a href="#catalog" className="btn btn--primary btn--large">Выбрать масло</a>
                {rating ? (
                  <a href={info?.avito_profile_url || '#reviews'} className="hero__rating"
                    {...(info?.avito_profile_url ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
                    <Stars value={rating} size={16} />
                    <span>
                      <strong>{ratingLabel(rating)}</strong>
                      {info?.avito_reviews_count
                        ? ` · ${info.avito_reviews_count.toLocaleString('ru-RU')} ${reviewsWord(info.avito_reviews_count)} на Авито`
                        : ' на Авито'}
                    </span>
                  </a>
                ) : null}
              </div>
            </div>
            {gallery.length ? (
              <div className={`hero__gallery hero__gallery--${gallery.length}`} aria-hidden="true">
                {gallery.map((product) => (
                  <img key={product.name} src={product.image} alt="" />
                ))}
              </div>
            ) : null}
          </div>
        </section>

        <section className="facts container" aria-label="Почему у нас">
          <div className="fact"><strong>Холодный отжим</strong><span>Без нагрева и рафинации</span></div>
          <div className="fact"><strong>Под заказ</strong><span>Отжимаем партиями, не держим месяцами</span></div>
          <div className="fact"><strong>Любая доставка</strong><span>Самовывоз, курьер, СДЭК, Почта</span></div>
        </section>

        <section className="section container" id="catalog" aria-labelledby="catalog-title">
          <div className="section__head">
            <p className="eyebrow">Каталог</p>
            <h2 id="catalog-title" className="section__title">Наши масла</h2>
          </div>
          {error ? (
            <div className="state">
              {error}
              {info?.phone ? (
                <> Позвоните нам: <a href={`tel:${phoneDigits(info.phone)}`}>{info.phone}</a></>
              ) : null}
            </div>
          ) : !products ? (
            <SkeletonGrid />
          ) : !products.length ? (
            <div className="state">Каталог скоро появится.</div>
          ) : (
            <div className="catalog">
              {products.map((product) => (
                <ProductCard key={product.name} product={product} inCart={inCartCount(product.name)}
                  onAdd={addToCart} />
              ))}
            </div>
          )}
        </section>

        <div className="container">
          <Reviews reviews={reviews} info={info} />
        </div>

        <section className="section container" id="delivery" aria-labelledby="delivery-title">
          <div className="section__head">
            <p className="eyebrow">Доставка и оплата</p>
            <h2 id="delivery-title" className="section__title">Как получить заказ</h2>
          </div>
          <div className="delivery">
            {(info?.delivery_methods || []).map((method) => (
              <div key={method.id} className="delivery__card">
                <h3>{method.label}</h3>
                <p>
                  {method.id === 'pickup' && info?.pickup_address
                    ? `Адрес: ${info.pickup_address}`
                    : DELIVERY_TEXT[method.id]}
                </p>
              </div>
            ))}
          </div>
          <p className="delivery__note">
            После заказа мы позвоним, подтвердим наличие и срок, назовём стоимость доставки и договоримся об оплате.
          </p>
        </section>
      </main>

      <footer className="footer">
        <div className="container footer__inner">
          <div className="brand brand--muted">
            <span className="brand__mark"><DropIcon size={16} /></span>
            {companyName}
          </div>
          <div className="footer__links">
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

      <CartPanel open={cartOpen} onClose={closeCart} cart={cart} priced={priced} info={info} />
    </div>
  )
}
