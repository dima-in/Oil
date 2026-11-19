// Названия в прайсе короткие («льняное», «черного тмина») — для покупателя дописываем «масло».
const SPECIAL_TITLES = {
  'кунжут черный': 'Масло чёрного кунжута',
  'кунжут нешлифованный': 'Масло нешлифованного кунжута',
}

const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1)

export function productTitle(name) {
  const clean = String(name || '').trim()
  const key = clean.toLowerCase().replace(/ё/g, 'е')
  if (SPECIAL_TITLES[key]) return SPECIAL_TITLES[key]
  if (key.startsWith('масло')) return capitalize(clean)
  if (!key.includes(' ') && /(ое|ее)$/.test(key)) return `${capitalize(clean)} масло`
  return `Масло ${clean}`
}

export function volumeLabel(ml) {
  const value = Number(ml)
  if (value >= 1000) return `${(value / 1000).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} л`
  return `${value} мл`
}

export function money(value) {
  return `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`
}

export function ratingLabel(value) {
  return Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

export function reviewsWord(count) {
  const n = Math.abs(Number(count)) % 100
  const last = n % 10
  if (n > 10 && n < 20) return 'отзывов'
  if (last === 1) return 'отзыв'
  if (last >= 2 && last <= 4) return 'отзыва'
  return 'отзывов'
}

export function dateLabel(iso) {
  if (!iso) return ''
  const date = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

// «23 ноября» — год только если не текущий; без «г.» на конце, чтобы дата вставала в предложение.
export function shortDate(iso) {
  if (!iso) return ''
  const date = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  const label = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
  return date.getFullYear() === new Date().getFullYear() ? label : `${label} ${date.getFullYear()}`
}

export function phoneDigits(phone) {
  return String(phone || '').replace(/\D/g, '')
}
