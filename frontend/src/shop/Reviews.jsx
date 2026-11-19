import { useState } from 'react'
import { dateLabel, ratingLabel, reviewsWord } from './format'

const PAGE = 6

export function Stars({ value, size = 16 }) {
  const rounded = Math.round(Number(value) || 0)
  return (
    <span className="stars" role="img" aria-label={`Оценка ${value || '—'} из 5`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <svg key={star} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"
          className={star <= rounded ? 'star star--on' : 'star'}>
          <path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z" />
        </svg>
      ))}
    </span>
  )
}

export function RatingBadge({ info, compact = false }) {
  const rating = info?.avito_rating
  if (!rating) return null
  const count = info?.avito_reviews_count
  const content = (
    <>
      <Stars value={rating} size={compact ? 15 : 18} />
      <span>
        <strong>{ratingLabel(rating)}</strong>
        {count ? ` · ${count.toLocaleString('ru-RU')} ${reviewsWord(count)} на Авито` : ' на Авито'}
      </span>
    </>
  )
  return info?.avito_profile_url ? (
    <a className="rating-badge" href={info.avito_profile_url} target="_blank" rel="noopener noreferrer">{content}</a>
  ) : (
    <span className="rating-badge">{content}</span>
  )
}

function ReviewCard({ review }) {
  const [open, setOpen] = useState(false)
  const long = review.text.length > 320
  return (
    <article className="review">
      <div className="review__head">
        {review.rating ? <Stars value={review.rating} size={15} /> : null}
        <span className="review__source">{review.source_label}</span>
      </div>
      <p className={long && !open ? 'review__text review__text--clamped' : 'review__text'}>{review.text}</p>
      {long ? (
        <button type="button" className="link-button" onClick={() => setOpen((value) => !value)}>
          {open ? 'Свернуть' : 'Читать полностью'}
        </button>
      ) : null}
      <div className="review__meta">
        <strong>{review.author}</strong>
        {review.review_date ? <span>{dateLabel(review.review_date)}</span> : null}
      </div>
      {review.item_title ? <div className="review__item">{review.item_title}</div> : null}
      {review.reply ? (
        <div className="review__reply">
          <span>Ответ мастерской</span>
          {review.reply}
        </div>
      ) : null}
    </article>
  )
}

export function ReviewList({ reviews, page = PAGE }) {
  const [shown, setShown] = useState(page)
  return (
    <>
      <div className="reviews">
        {reviews.slice(0, shown).map((review) => <ReviewCard key={review.id} review={review} />)}
      </div>
      {shown < reviews.length ? (
        <div className="section__actions">
          <button type="button" className="btn btn--chalk" onClick={() => setShown((value) => value + page)}>
            Показать ещё отзывы
          </button>
        </div>
      ) : null}
    </>
  )
}

export default function Reviews({ reviews, info }) {
  const rating = info?.avito_rating
  if (!reviews.length && !rating) return null

  return (
    <section className="section" id="reviews" aria-labelledby="reviews-title">
      <div className="section__head section__head--split">
        <div>
          <p className="eyebrow">отзывы</p>
          <h2 id="reviews-title" className="section__title">Что говорят покупатели</h2>
        </div>
        {rating ? (
          <div className="rating-summary">
            <div className="rating-summary__value">{ratingLabel(rating)}</div>
            <div>
              <Stars value={rating} size={20} />
              <div className="rating-summary__text">
                {info?.avito_reviews_count
                  ? `${info.avito_reviews_count.toLocaleString('ru-RU')} ${reviewsWord(info.avito_reviews_count)} на Авито`
                  : 'рейтинг на Авито'}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {reviews.length ? <ReviewList reviews={reviews} /> : null}

      {info?.avito_profile_url ? (
        <div className="section__actions">
          <a className="btn btn--chalk" href={info.avito_profile_url} target="_blank" rel="noopener noreferrer">
            Все отзывы на Авито ↗
          </a>
        </div>
      ) : null}
    </section>
  )
}
