// Публичные ручки витрины: без входа и без токена CRM.
async function request(path, options = {}) {
  const response = await fetch(`/api/shop${path}`, {
    ...options,
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail
    const error = new Error(typeof detail === 'string' ? detail : 'Не получилось. Попробуйте ещё раз или позвоните нам.')
    error.status = response.status
    throw error
  }
  return payload
}

export const shopApi = {
  info: () => request('/info'),
  catalog: () => request('/catalog'),
  product: (slug) => request(`/products/${encodeURIComponent(slug)}`),
  reviews: (limit = 60) => request(`/reviews?limit=${limit}`),
  placeOrder: (order) => request('/orders', { method: 'POST', body: JSON.stringify(order) }),
}
