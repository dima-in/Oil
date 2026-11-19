import { ratingLabel, reviewsWord } from './format'

// Меловые значки — свои, не картинки Авито: на сайте показываем факты из профиля.
const ICONS = {
  trusted: 'M12 2.5 4 5.5v6c0 4.6 3.3 8.6 8 10 4.7-1.4 8-5.4 8-10v-6zM8.5 12l2.5 2.5 4.8-5',
  star: 'M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z',
  box: 'M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8M7.5 5.5l9 5',
  since: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 15h3',
}

function Badge({ icon, title, text, href }) {
  const body = (
    <>
      <span className="badge-icon" aria-hidden="true">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"
          strokeLinecap="round" strokeLinejoin="round">
          <path d={ICONS[icon]} />
        </svg>
      </span>
      <span className="trust-badge__title">{title}</span>
      {text ? <span className="trust-badge__text">{text}</span> : null}
    </>
  )
  return href ? (
    <a className="trust-badge" href={href} target="_blank" rel="noopener noreferrer">{body}</a>
  ) : (
    <div className="trust-badge">{body}</div>
  )
}

function salesWord(count) {
  const n = Math.abs(Number(count)) % 100
  const last = n % 10
  if (n > 10 && n < 20) return 'продаж'
  if (last === 1) return 'продажа'
  if (last >= 2 && last <= 4) return 'продажи'
  return 'продаж'
}

export default function TrustBadges({ info }) {
  if (!info) return null
  const profile = info.avito_profile_url
  const badges = []
  if (info.avito_trusted) badges.push({ icon: 'trusted', title: 'Надёжный продавец', text: 'статус на Авито' })
  if (info.avito_rating) {
    badges.push({
      icon: 'star',
      title: `${ratingLabel(info.avito_rating)} из 5`,
      text: info.avito_reviews_count
        ? `${info.avito_reviews_count.toLocaleString('ru-RU')} ${reviewsWord(info.avito_reviews_count)}`
        : 'рейтинг на Авито',
    })
  }
  if (info.avito_sales_count) {
    badges.push({
      icon: 'box',
      title: `${info.avito_sales_count.toLocaleString('ru-RU')} ${salesWord(info.avito_sales_count)}`,
      text: 'с Авито Доставкой',
    })
  }
  if (info.avito_since) badges.push({ icon: 'since', title: `с ${info.avito_since} года`, text: 'продаём на Авито' })
  if (!badges.length) return null

  return (
    <section className="trust container" aria-label="Нам доверяют на Авито">
      {badges.map((badge) => <Badge key={badge.icon} {...badge} href={profile} />)}
    </section>
  )
}
