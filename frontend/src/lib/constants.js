export const API_BASE = '/api'

export const ADMIN_CREDENTIALS = {
  username: 'oilpress',
  password: 'MarshallJCM800',
}

export const STATUS_OPTIONS = [
  { value: '0', label: 'новый', tone: 'blue' },
  { value: '1', label: 'получена предоплата', tone: 'green' },
  { value: '2', label: 'Avito доставка', tone: 'amber' },
  { value: '3', label: 'Ozon', tone: 'slate' },
  { value: '4', label: 'завершен', tone: 'green' },
  { value: '5', label: 'готов к выдаче', tone: 'blue' },
  { value: '6', label: 'отменен', tone: 'red' },
  { value: '7', label: 'ожидает предоплаты', tone: 'amber' },
]

export const STATUS_MAP = Object.fromEntries(
  STATUS_OPTIONS.map((status) => [status.value, status]),
)

export const INITIAL_CUSTOMER_FORM = () => ({
  name: '',
  surname: '',
  phone: '',
  address: '',
  status: '0',
  shipping_date: new Date().toISOString().split('T')[0],
})

export const NAV_ITEMS = [
  { path: '/', label: 'Каталог', shortLabel: 'Каталог', icon: 'OP' },
  { path: '/orders', label: 'Заказы', shortLabel: 'Заказы', icon: 'OR' },
  { path: '/admin', label: 'Админ', shortLabel: 'Админ', icon: 'AD' },
]
