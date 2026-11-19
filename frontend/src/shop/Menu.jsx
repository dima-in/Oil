import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { phoneDigits } from './format'

const SECTIONS = [
  ['/#catalog', 'Масла'],
  ['/#about', 'Мастерская'],
  ['/#reviews', 'Отзывы'],
  ['/#delivery', 'Доставка'],
]

// Меню для телефона: открывается по логотипу в шапке, выезжает слева.
export default function Menu({ open, onClose, info, products, shopName }) {
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.classList.add('no-scroll')
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('no-scroll')
    }
  }, [open, onClose])

  return (
    <div id="site-menu" className={open ? 'drawer drawer--left drawer--open' : 'drawer drawer--left'}
      aria-hidden={!open} inert={!open}>
      <div className="drawer__backdrop" onClick={onClose} />
      <aside className="drawer__panel menu" role="dialog" aria-modal="true" aria-label="Меню">
        <header className="drawer__head">
          <Link to="/" className="brand" onClick={onClose}>
            <img src="/static/images/brand/logo.png" alt="" className="brand__logo" />
            <span className="brand__name">{shopName}</span>
          </Link>
          <button ref={closeRef} type="button" className="icon-button" aria-label="Закрыть меню" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="drawer__body">
          <nav className="menu__sections" aria-label="Разделы">
            {SECTIONS.map(([to, label]) => <Link key={to} to={to} onClick={onClose}>{label}</Link>)}
          </nav>

          {products?.length ? (
            <nav className="menu__oils" aria-label="Масла">
              <p className="eyebrow">все масла</p>
              {products.map((product) => (
                <Link key={product.slug} to={`/p/${product.slug}`} onClick={onClose}>{product.title}</Link>
              ))}
            </nav>
          ) : null}

          <div className="menu__contacts">
            {info?.phone ? <a href={`tel:${phoneDigits(info.phone)}`}>{info.phone}</a> : null}
            {info?.pickup_address ? <span>{info.pickup_address}</span> : null}
            {info?.avito_profile_url ? (
              <a href={info.avito_profile_url} target="_blank" rel="noopener noreferrer">Мы на Авито ↗</a>
            ) : null}
          </div>
        </div>
      </aside>
    </div>
  )
}
