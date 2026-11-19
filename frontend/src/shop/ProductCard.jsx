import { useState } from 'react'
import { money, productTitle, volumeLabel } from './format'

export function DropIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2.7s-6 6.6-6 11.3a6 6 0 0 0 12 0c0-4.7-6-11.3-6-11.3z" />
    </svg>
  )
}

export default function ProductCard({ product, inCart, onAdd }) {
  const [selected, setSelected] = useState(product.variants[0]?.volume)
  const [count, setCount] = useState(1)
  const [imageFailed, setImageFailed] = useState(false)
  const variant = product.variants.find((item) => item.volume === selected) || product.variants[0]
  const title = productTitle(product.name)

  const add = () => {
    onAdd(product.name, variant.volume, count)
    setCount(1)
  }

  return (
    <article className="product">
      <div className="product__media">
        {product.image && !imageFailed ? (
          <img src={product.image} alt={title} loading="lazy" onError={() => setImageFailed(true)} />
        ) : (
          <div className="product__placeholder" aria-hidden="true">
            <DropIcon size={40} />
          </div>
        )}
        <span className={variant.in_stock ? 'badge badge--stock' : 'badge'}>
          {variant.in_stock ? 'В наличии' : 'Отожмём под заказ'}
        </span>
      </div>

      <div className="product__body">
        <h3 className="product__title">{title}</h3>

        <div className="volumes" role="radiogroup" aria-label={`Объём: ${title}`}>
          {product.variants.map((item) => (
            <button
              key={item.volume}
              type="button"
              role="radio"
              aria-checked={item.volume === variant.volume}
              className={item.volume === variant.volume ? 'volume volume--active' : 'volume'}
              onClick={() => setSelected(item.volume)}
            >
              {volumeLabel(item.volume)}
            </button>
          ))}
        </div>

        <div className="product__buy">
          <div className="product__price">{money(variant.price)}</div>
          <div className="stepper" aria-label="Количество">
            <button type="button" aria-label="Меньше" onClick={() => setCount((value) => Math.max(1, value - 1))}>
              −
            </button>
            <span aria-live="polite">{count}</span>
            <button type="button" aria-label="Больше" onClick={() => setCount((value) => Math.min(50, value + 1))}>
              +
            </button>
          </div>
        </div>

        <button type="button" className="btn btn--primary btn--block" onClick={add}>
          {inCart ? `В корзину · уже ${inCart}` : 'В корзину'}
        </button>
      </div>
    </article>
  )
}
