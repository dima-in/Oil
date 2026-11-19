import { useState } from 'react'
import { Link } from 'react-router-dom'
import { money, volumeLabel } from './format'

export function DropIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2.7s-6 6.6-6 11.3a6 6 0 0 0 12 0c0-4.7-6-11.3-6-11.3z" />
    </svg>
  )
}

// Фото в бумажной рамке, как этикетка на полке мастерской. Есть меловой рисунок сырья —
// фото приколото к доске, а рисунок рядом; children — наклейка на фото.
export function ProductPhoto({ product, large = false, children = null }) {
  const [failed, setFailed] = useState(false)
  const [sketchFailed, setSketchFailed] = useState(false)
  const scene = product.sketch && !sketchFailed
  const photo = (
    <div className={large ? 'photo photo--large' : 'photo'}>
      {product.image && !failed ? (
        <img src={product.image} alt={product.title} loading={large ? 'eager' : 'lazy'} onError={() => setFailed(true)} />
      ) : (
        <div className="photo__empty" aria-hidden="true">
          <DropIcon size={44} />
        </div>
      )}
      {children}
    </div>
  )
  if (!scene) return photo
  return (
    <div className={large ? 'scene scene--large' : 'scene'}>
      <img className="scene__sketch" src={product.sketch} alt="" loading={large ? 'eager' : 'lazy'}
        onError={() => setSketchFailed(true)} />
      {photo}
    </div>
  )
}

export function VolumePicker({ product, value, onChange }) {
  return (
    <div className="volumes" role="radiogroup" aria-label={`Объём: ${product.title}`}>
      {product.variants.map((item) => (
        <button key={item.volume} type="button" role="radio" aria-checked={item.volume === value}
          className={item.volume === value ? 'volume volume--active' : 'volume'} onClick={() => onChange(item.volume)}>
          {volumeLabel(item.volume)}
        </button>
      ))}
    </div>
  )
}

export function PriceTag({ price }) {
  return <span className="price-tag">{money(price)}</span>
}

export function Stepper({ value, onChange, small = false }) {
  return (
    <div className={small ? 'stepper stepper--small' : 'stepper'} aria-label="Количество">
      <button type="button" aria-label="Меньше" onClick={() => onChange(Math.max(1, value - 1))}>−</button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label="Больше" onClick={() => onChange(Math.min(50, value + 1))}>+</button>
    </div>
  )
}

export default function ProductCard({ product, inCart, onAdd }) {
  const [selected, setSelected] = useState(product.variants[0]?.volume)
  const [count, setCount] = useState(1)
  const variant = product.variants.find((item) => item.volume === selected) || product.variants[0]
  const link = `/p/${product.slug}`

  return (
    <article className="product">
      <Link to={link} className="product__photo-link" aria-label={product.title}>
        <ProductPhoto product={product}>
          <span className={variant.in_stock ? 'sticker sticker--stock' : 'sticker'}>
            {variant.in_stock ? 'есть в наличии' : 'отожмём под заказ'}
          </span>
        </ProductPhoto>
      </Link>

      <div className="product__body">
        <h3 className="product__title">
          <Link to={link}>{product.title}</Link>
        </h3>
        {product.short_text ? <p className="product__lead">{product.short_text}</p> : null}

        <VolumePicker product={product} value={variant.volume} onChange={setSelected} />

        <div className="product__buy">
          <PriceTag price={variant.price} />
          <Stepper value={count} onChange={setCount} />
        </div>

        <button type="button" className="btn btn--primary btn--block"
          onClick={() => { onAdd(product.name, variant.volume, count); setCount(1) }}>
          {inCart ? `В корзину · уже ${inCart}` : 'В корзину'}
        </button>
        <div className="product__links">
          <Link to={link}>Подробнее о масле</Link>
          {product.avito_url ? (
            <a href={product.avito_url} target="_blank" rel="noopener noreferrer">или на Авито ↗</a>
          ) : null}
        </div>
      </div>
    </article>
  )
}
