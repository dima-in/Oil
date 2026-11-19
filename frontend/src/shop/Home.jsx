import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import ProductCard from './ProductCard'
import Reviews, { RatingBadge } from './Reviews'
import TrustBadges from './Trust'
import { phoneDigits } from './format'

const PRINCIPLES = [
  ['Без металла и нагрева', 'Отжимаем гидравлическим прессом в бочонке — масло не греется и не окисляется'],
  ['Живое масло', 'Без фильтрации, добавок и консервантов — только семена и орехи'],
  ['Под ваш заказ', 'Отжимаем после заказа, от 3 дней — масло всегда свежее'],
]

const DELIVERY_TEXT = {
  pickup: (info) => (info?.pickup_address ? `${info.pickup_address}. Бесплатно.` : 'Адрес скажем при подтверждении.'),
  courier: () => 'По Москве в удобное время. Стоимость назовём при подтверждении.',
  cdek: () => 'СДЭК, Boxberry и другие — по России и за её пределы. До транспортной компании довезём бесплатно.',
  post: () => 'В любой город России, за счёт получателя.',
}

function SkeletonGrid() {
  return (
    <div className="catalog" aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => <div key={index} className="product product--skeleton" />)}
    </div>
  )
}

export default function Home({ info, products, reviews, error, inCartCount, onAdd }) {
  const location = useLocation()

  // Переход «Каталог», «Отзывы» со страницы масла: прокрутить к разделу, когда он отрисован.
  useEffect(() => {
    if (!location.hash) return
    const target = document.getElementById(location.hash.slice(1))
    if (target) target.scrollIntoView()
  }, [location.hash, products])

  const aboutParagraphs = (info?.about || '').split(/\n\s*\n/).filter(Boolean)

  return (
    <>
      <section className="hero">
        <div className="container hero__inner">
          <div className="hero__text">
            <img className="hero__logo" src="/static/images/brand/logo.png" alt={info?.shop_name || 'Выжимальня'} />
            <h1>Масла холодного отжима</h1>
            <p className="hero__lead">
              Сыродавленные «живые» масла: отжимаем гидравлическим прессом в бочонке, без нагрева и металла —
              под ваш заказ.
            </p>
            <div className="hero__actions">
              <a href="#catalog" className="btn btn--primary btn--large">Выбрать масло</a>
              <RatingBadge info={info} />
            </div>
          </div>
          <figure className="hero__picture">
            <img src="/static/images/brand/hero.webp" alt="Облепиховое масло и паста в банке на деревянном столе" />
          </figure>
        </div>
      </section>

      <TrustBadges info={info} />

      <section className="section container" id="catalog" aria-labelledby="catalog-title">
        <div className="section__head">
          <p className="eyebrow">каталог</p>
          <h2 id="catalog-title" className="section__title">Наши масла</h2>
        </div>
        {error ? (
          <div className="state">
            {error}
            {info?.phone ? <> Позвоните нам: <a href={`tel:${phoneDigits(info.phone)}`}>{info.phone}</a></> : null}
          </div>
        ) : !products ? (
          <SkeletonGrid />
        ) : !products.length ? (
          <div className="state">Каталог скоро появится.</div>
        ) : (
          <div className="catalog">
            {products.map((product) => (
              <ProductCard key={product.slug} product={product} inCart={inCartCount(product.name)} onAdd={onAdd} />
            ))}
          </div>
        )}
      </section>

      <section className="section container about" id="about" aria-labelledby="about-title">
        <div className="section__head">
          <p className="eyebrow">мастерская</p>
          <h2 id="about-title" className="section__title">Как мы отжимаем</h2>
        </div>
        {info?.workshop_photos?.length ? (
          <div className="workshop">
            {info.workshop_photos.map((photo) => (
              <figure key={photo.src} className="workshop__photo">
                <img src={photo.src} alt={photo.caption || 'Мастерская'} loading="lazy" />
                {photo.caption ? <figcaption>{photo.caption}</figcaption> : null}
              </figure>
            ))}
          </div>
        ) : null}
        <div className="about__grid">
          <div className="about__text">
            {aboutParagraphs.map((paragraph) => <p key={paragraph.slice(0, 40)}>{paragraph}</p>)}
          </div>
          <ul className="principles">
            {PRINCIPLES.map(([title, text]) => (
              <li key={title}>
                <strong>{title}</strong>
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className="container">
        <Reviews reviews={reviews} info={info} />
      </div>

      <section className="section container" id="delivery" aria-labelledby="delivery-title">
        <div className="section__head">
          <p className="eyebrow">доставка и оплата</p>
          <h2 id="delivery-title" className="section__title">Как получить заказ</h2>
        </div>
        <div className="delivery">
          {(info?.delivery_methods || []).map((method) => (
            <div key={method.id} className="delivery__card">
              <h3>{method.label}</h3>
              <p>{DELIVERY_TEXT[method.id]?.(info)}</p>
            </div>
          ))}
          {info?.avito_profile_url ? (
            <a className="delivery__card delivery__card--avito" href={info.avito_profile_url} target="_blank"
              rel="noopener noreferrer">
              <h3>Авито Доставка ↗</h3>
              <p>Удобнее через Авито? Закажите любое масло в нашем профиле — с Авито Доставкой.</p>
            </a>
          ) : null}
        </div>
        <p className="delivery__note">
          После заказа на сайте мы позвоним, подтвердим наличие и срок, назовём стоимость доставки и договоримся
          об оплате.
        </p>
      </section>
    </>
  )
}
