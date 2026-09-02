import { ADMIN_CREDENTIALS, API_BASE } from './constants'

const basicAuthHeader = () =>
  `Basic ${btoa(`${ADMIN_CREDENTIALS.username}:${ADMIN_CREDENTIALS.password}`)}`

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    return response.json()
  }

  const text = await response.text()
  return text ? { detail: text } : null
}

async function request(path, options = {}) {
  const { auth = false, headers, ...rest } = options
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(headers || {}),
      ...(auth ? { Authorization: basicAuthHeader() } : {}),
    },
  })

  const payload = await parseResponse(response)

  if (!response.ok) {
    const message =
      payload?.detail ||
      payload?.message ||
      `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return payload
}

export const api = {
  getCatalog: () => request('/catalog'),
  getOrders: () => request('/orders', { auth: true }),
  createOrder: (order) =>
    request('/order', {
      method: 'POST',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(order),
    }),
  deleteOrder: (id) =>
    request(`/order/${id}`, {
      method: 'DELETE',
      auth: true,
    }),
  getPricelist: () => request('/admin/pricelist', { auth: true }),
  addPriceItem: (item) =>
    request('/admin/pricelist', {
      method: 'POST',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(item),
    }),
  updatePrice: (id, payload) =>
    request(`/admin/pricelist/${id}`, {
      method: 'PUT',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deletePrice: (id) =>
    request(`/admin/pricelist/${id}`, {
      method: 'DELETE',
      auth: true,
    }),
  clearPricelist: () =>
    request('/admin/pricelist/clear', {
      method: 'POST',
      auth: true,
    }),
  uploadPricelist: (formData) =>
    request('/admin/upload-pricelist', {
      method: 'POST',
      auth: true,
      body: formData,
    }),
  getAnalytics: ({ period, dateFrom, dateTo }) => {
    const params = new URLSearchParams()
    if (period) params.set('period', period)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    const query = params.toString()
    return request(`/admin/analytics${query ? `?${query}` : ''}`, { auth: true })
  },
  getExpenses: ({ dateFrom, dateTo }) => {
    const params = new URLSearchParams()
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    const query = params.toString()
    return request(`/admin/expenses${query ? `?${query}` : ''}`, { auth: true })
  },
  addExpense: (payload) =>
    request('/admin/expenses', {
      method: 'POST',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteExpense: (id) =>
    request(`/admin/expenses/${id}`, {
      method: 'DELETE',
      auth: true,
    }),
  getProductionBatches: ({ dateFrom, dateTo }) => {
    const params = new URLSearchParams()
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    const query = params.toString()
    return request(`/admin/production-batches${query ? `?${query}` : ''}`, { auth: true })
  },
  getProductionProfiles: () => request('/admin/production-profiles', { auth: true }),
  saveProductionProfile: (payload) =>
    request('/admin/production-profiles', {
      method: 'POST',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteProductionProfile: (id) =>
    request(`/admin/production-profiles/${id}`, {
      method: 'DELETE',
      auth: true,
    }),
  addProductionBatch: (payload) =>
    request('/admin/production-batches', {
      method: 'POST',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteProductionBatch: (id) =>
    request(`/admin/production-batches/${id}`, {
      method: 'DELETE',
      auth: true,
    }),
  askAssistant: (question) =>
    request('/analytics/assistant', {
      method: 'POST',
      auth: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }),
}

export const fetchCustomerAnalytics = async (params = {}) => {
  const { period, dateFrom, dateTo } = params
  const queryParams = new URLSearchParams()
  if (period) queryParams.set('period', period)
  if (dateFrom) queryParams.set('date_from', dateFrom)
  if (dateTo) queryParams.set('date_to', dateTo)
  const query = queryParams.toString()
  const url = `${API_BASE}/analytics/customers${query ? `?${query}` : ''}`
  const response = await fetch(url, {
    headers: {
      Authorization: basicAuthHeader(),
    },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch customer analytics: ${response.status}`)
  }
  return await response.json()
}

export const fetchProductAnalytics = async (params = {}) => {
  const { period, dateFrom, dateTo } = params
  const queryParams = new URLSearchParams()
  if (period) queryParams.set('period', period)
  if (dateFrom) queryParams.set('date_from', dateFrom)
  if (dateTo) queryParams.set('date_to', dateTo)
  const query = queryParams.toString()
  const url = `${API_BASE}/analytics/products${query ? `?${query}` : ''}`
  const response = await fetch(url, {
    headers: {
      Authorization: basicAuthHeader(),
    },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch product analytics: ${response.status}`)
  }
  return await response.json()
}

export const fetchSummaryAnalytics = async (params = {}) => {
  const { period, dateFrom, dateTo } = params
  const queryParams = new URLSearchParams()
  if (period) queryParams.set('period', period)
  if (dateFrom) queryParams.set('date_from', dateFrom)
  if (dateTo) queryParams.set('date_to', dateTo)
  const query = queryParams.toString()
  const url = `${API_BASE}/analytics/summary${query ? `?${query}` : ''}`
  const response = await fetch(url, {
    headers: {
      Authorization: basicAuthHeader(),
    },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch summary analytics: ${response.status}`)
  }
  return await response.json()
}
