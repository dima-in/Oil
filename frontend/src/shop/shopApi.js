// Публичные ручки витрины: без входа и без токена CRM.
async function request(path, options = {}) {
  const response = await fetch(`/api/shop${path}`, {
    ...options,
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail
    throw new Error(typeof detail === 'string' ? detail : 'Не получилось. Попробуйте ещё раз или позвоните нам.')
  }
  return payload
}

export const shopApi = {
  info: () => request('/info'),
  catalog: () => request('/catalog'),
  reviews: (limit = 60) => request(`/reviews?limit=${limit}`),
  placeOrder: (order) => request('/orders', { method: 'POST', body: JSON.stringify(order) }),
}
