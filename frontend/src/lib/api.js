import { API_BASE } from './constants'
import { clearSession, getToken } from './auth'

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    return response.json()
  }

  const text = await response.text()
  return text ? { detail: text } : null
}

function query(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function request(path, options = {}) {
  const { auth = true, json, headers, ...rest } = options
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(headers || {}),
      ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(json !== undefined ? { body: JSON.stringify(json) } : {}),
  })

  const payload = await parseResponse(response)

  if (response.status === 401 && auth) {
    // Токен истёк или пользователя отключили — возвращаем на экран входа.
    clearSession()
  }

  if (!response.ok) {
    const detail = payload?.detail
    const message =
      (typeof detail === 'string' ? detail : null) ||
      payload?.message ||
      `Ошибка запроса (${response.status})`
    throw new Error(message)
  }

  return payload
}

export const api = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', auth: false, json: { username, password } }),
  me: () => request('/auth/me'),
  changePassword: (currentPassword, newPassword) =>
    request('/auth/password', {
      method: 'POST',
      json: { current_password: currentPassword, new_password: newPassword },
    }),
  listUsers: () => request('/users'),
  createUser: (payload) => request('/users', { method: 'POST', json: payload }),
  updateUser: (id, payload) => request(`/users/${id}`, { method: 'PATCH', json: payload }),

  getCatalog: () => request('/catalog', { auth: false }),
  getOrders: () => request('/orders'),
  createOrder: (order) => request('/order', { method: 'POST', json: order }),
  deleteOrder: (id) => request(`/order/${id}`, { method: 'DELETE' }),
  getPricelist: () => request('/admin/pricelist'),
  addPriceItem: (item) => request('/admin/pricelist', { method: 'POST', json: item }),
  updatePrice: (id, payload) => request(`/admin/pricelist/${id}`, { method: 'PUT', json: payload }),
  deletePrice: (id) => request(`/admin/pricelist/${id}`, { method: 'DELETE' }),
  clearPricelist: () => request('/admin/pricelist/clear', { method: 'POST' }),
  uploadPricelist: (formData) => request('/admin/upload-pricelist', { method: 'POST', body: formData }),
  getAnalytics: ({ period, dateFrom, dateTo }) =>
    request(`/admin/analytics${query({ period, date_from: dateFrom, date_to: dateTo })}`),
  getExpenses: ({ dateFrom, dateTo }) =>
    request(`/admin/expenses${query({ date_from: dateFrom, date_to: dateTo })}`),
  addExpense: (payload) => request('/admin/expenses', { method: 'POST', json: payload }),
  deleteExpense: (id) => request(`/admin/expenses/${id}`, { method: 'DELETE' }),
  getProductionBatches: ({ dateFrom, dateTo }) =>
    request(`/admin/production-batches${query({ date_from: dateFrom, date_to: dateTo })}`),
  getProductionProfiles: () => request('/admin/production-profiles'),
  saveProductionProfile: (payload) => request('/admin/production-profiles', { method: 'POST', json: payload }),
  deleteProductionProfile: (id) => request(`/admin/production-profiles/${id}`, { method: 'DELETE' }),
  addProductionBatch: (payload) => request('/admin/production-batches', { method: 'POST', json: payload }),
  deleteProductionBatch: (id) => request(`/admin/production-batches/${id}`, { method: 'DELETE' }),

  crm: {
    dashboard: () => request('/crm/dashboard'),
    statuses: () => request('/crm/statuses'),
    orders: (params) => request(`/crm/orders${query(params)}`),
    createOrder: (payload) => request('/crm/orders', { method: 'POST', json: payload }),
    settings: () => request('/crm/settings'),
    updateSettings: (payload) => request('/crm/settings', { method: 'PATCH', json: payload }),
    productionSchedule: (days) => request(`/crm/production-schedule${query({ days })}`),
    order: (id) => request(`/crm/orders/${id}`),
    updateOrder: (id, payload) => request(`/crm/orders/${id}`, { method: 'PATCH', json: payload }),
    customers: (q) => request(`/crm/customers${query({ q })}`),
    customer: (id) => request(`/crm/customers/${id}`),
    createCustomer: (payload) => request('/crm/customers', { method: 'POST', json: payload }),
    updateCustomer: (id, payload) => request(`/crm/customers/${id}`, { method: 'PATCH', json: payload }),
    addInteraction: (id, payload) =>
      request(`/crm/customers/${id}/interactions`, { method: 'POST', json: payload }),
    tasks: (params) => request(`/crm/tasks${query(params)}`),
    createTask: (payload) => request('/crm/tasks', { method: 'POST', json: payload }),
    updateTask: (id, payload) => request(`/crm/tasks/${id}`, { method: 'PATCH', json: payload }),
    deleteTask: (id) => request(`/crm/tasks/${id}`, { method: 'DELETE' }),
    stock: () => request('/crm/stock'),
    productionNeeds: (days) => request(`/crm/production-needs${query({ days })}`),
  },

  assistant: {
    status: () => request('/assistant/status'),
    chat: (messages, context) => request('/assistant/chat', { method: 'POST', json: { messages, context } }),
    parseOrder: (text) => request('/assistant/parse-order', { method: 'POST', json: { text } }),
    confirm: (id) => request(`/assistant/actions/${id}/confirm`, { method: 'POST' }),
    cancel: (id) => request(`/assistant/actions/${id}/cancel`, { method: 'POST' }),
  },
}

// Ручки /api/analytics/* принимают start_date / end_date (раньше сюда уходили date_from /
// date_to, и фильтр по датам молча не работал).
const analyticsQuery = ({ dateFrom, dateTo } = {}) => query({ start_date: dateFrom, end_date: dateTo })

export const fetchCustomerAnalytics = (params) => request(`/analytics/customers${analyticsQuery(params)}`)
export const fetchProductAnalytics = (params) => request(`/analytics/products${analyticsQuery(params)}`)
export const fetchSummaryAnalytics = (params) => request(`/analytics/summary${analyticsQuery(params)}`)
