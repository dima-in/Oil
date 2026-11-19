// Яндекс Метрика: номер счётчика кладёт в страницу сервер (templates/shop.html).
// Нет счётчика или его заблокировал браузер — вызовы просто ничего не делают.
export function metrika(...args) {
  const id = window.SHOP_METRIKA_ID
  if (id && typeof window.ym === 'function') window.ym(id, ...args)
}
