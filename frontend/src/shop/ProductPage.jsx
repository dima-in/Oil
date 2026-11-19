import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ProductCard, { PriceTag, ProductPhoto, Stepper, VolumePicker } from './ProductCard'
import { ReviewList } from './Reviews'
import { shopApi } from './shopApi'

function ProductDetails({ product, info, inCart, onAdd }) {
  const [selected, setSelected] = useState(product.variants[0]?.volume)
  const [count, setCount] = useState(1)
  const variant = product.variants.find((item) => item.volume === selected) || product.variants[0]
  const paragraphs = (product.description || '').split(/\n\s*\n/).filter(Boolean)

  return (
    <>
      <div className="item">
        <div className="item__media">
          <ProductPhoto product={product} large />
        </div>
        <div className="item__info">
          <p className="eyebrow">сыродавленное · холодный отжим</p>
          <h1 className="item__title">{product.title}</h1>
          {product.short_text ? <p className="item__lead">{product.short_text}</p> : null}

          {variant ? (
            <div className="item__buy">
              <VolumePicker product={product} value={variant.volume} onChange={setSelected} />
              <div className="product__buy">
                <PriceTag price={variant.price} />
                <Stepper value={count} onChange={setCount} />
              </div>
              <p className={variant.in_stock ? 'item__stock item__stock--yes' : 'item__stock'}>
                {variant.in_stock ? 'Есть в наличии' : 'Отожмём под ваш заказ — от 3 дней'}
              </p>
              <button type="button" className="btn btn--primary btn--large btn--block"
                onClick={() => { onAdd(product.name, variant.volume, count); setCount(1) }}>
                {inCart ? `Добавить в корзину · уже ${inCart}` : 'Добавить в корзину'}
              </button>
              {product.avito_url ? (
                <a className="btn btn--chalk btn--block" href={product.avito_url} target="_blank" rel="noopener noreferrer">
                  Купить на Авито — с Авито Доставкой ↗
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <section className="section item__about" aria-labelledby="item-about-title">
        <h2 id="item-about-title" className="section__title">О масле</h2>
        <div className="item__description">
          {paragraphs.length ? (
            paragraphs.map((paragraph) => <p key={paragraph.slice(0, 40)}>{paragraph}</p>)
          ) : (
            <p>
              Сыродавленное «живое» масло: отжимаем гидравлическим прессом в бочонке, без нагрева и контакта с металлом,
              без фильтрации и консервантов — под ваш заказ.
            </p>
          )}
          {info?.pickup_address ? (
            <p className="item__pickup">Самовывоз: {info.pickup_address}. Доставка — курьером, СДЭК, Почтой России.</p>
          ) : null}
        </div>
      </section>

      {product.reviews?.length ? (
        <section className="section" aria-labelledby="item-reviews-title">
          <h2 id="item-reviews-title" className="section__title">Отзывы об этом масле</h2>
          <ReviewList reviews={product.reviews} page={3} />
        </section>
      ) : null}
    </>
  )
}

export default function ProductPage({ info, products, inCartCount, onAdd }) {
  const { slug } = useParams()
  // Ответ помнит, к какому адресу он относится: при переходе на другое масло старый не показываем.
  const [loaded, setLoaded] = useState({ slug: null, product: null, error: null })

  useEffect(() => {
    let alive = true
    shopApi
      .product(slug)
      .then((data) => alive && setLoaded({ slug, product: data, error: null }))
      .catch((requestError) => alive && setLoaded({ slug, product: null, error: requestError }))
    return () => {
      alive = false
    }
  }, [slug])

  const { product, error } = loaded.slug === slug ? loaded : { product: null, error: null }

  useEffect(() => {
    if (product?.title) document.title = `${product.title} — ${info?.shop_name || 'Выжимальня'}`
  }, [product, info])

  const others = (products || []).filter((item) => item.slug !== slug).slice(0, 4)

  return (
    <div className="container page">
      <Link to="/#catalog" className="back-link">← все масла</Link>
      {error ? (
        <div className="state">
          {error.status === 404 ? 'Такого масла нет в каталоге.' : error.message} <Link to="/">На главную</Link>
        </div>
      ) : !product ? (
        <div className="item item--loading" aria-hidden="true" />
      ) : (
        <ProductDetails key={product.slug} product={product} info={info} inCart={inCartCount(product.name)}
          onAdd={onAdd} />
      )}

      {others.length ? (
        <section className="section" aria-labelledby="others-title">
          <h2 id="others-title" className="section__title">Ещё из мастерской</h2>
          <div className="catalog catalog--compact">
            {others.map((item) => (
              <ProductCard key={item.slug} product={item} inCart={inCartCount(item.name)} onAdd={onAdd} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
