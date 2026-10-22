export function money(value) {
  return `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`
}

export function volume(ml) {
  if (ml === null || ml === undefined) return '—'
  const value = Number(ml)
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} л`
  }
  return `${Math.round(value).toLocaleString('ru-RU')} мл`
}

function toDate(iso) {
  if (!iso) return null
  // «ГГГГ-ММ-ДД» без времени разбираем как локальную дату, а не полночь UTC.
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
}

export function dateRu(iso) {
  const parsed = toDate(iso)
  return parsed ? parsed.toLocaleDateString('ru-RU') : '—'
}

export function dateTimeRu(iso) {
  const parsed = toDate(iso)
  return parsed
    ? parsed.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '—'
}

export function todayIso() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

export function addDaysIso(iso, days) {
  const parsed = toDate(iso)
  parsed.setDate(parsed.getDate() + days)
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

export function relativeDay(iso) {
  if (!iso) return ''
  const diff = Math.round((toDate(iso) - toDate(todayIso())) / 86400000)
  if (diff === 0) return 'сегодня'
  if (diff === 1) return 'завтра'
  if (diff === -1) return 'вчера'
  if (diff < 0) return `${-diff} дн. назад`
  return `через ${diff} дн.`
}

export function phoneHref(phone) {
  const digits = String(phone || '').replace(/[^\d+]/g, '')
  return digits ? `tel:${digits}` : undefined
}
