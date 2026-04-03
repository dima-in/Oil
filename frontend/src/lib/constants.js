export const API_BASE = '/api'

export const ADMIN_CREDENTIALS = {
  username: 'oilpress',
  password: 'MarshallJCM800',
}

export const STATUS_OPTIONS = [
  { value: '0', label: '\u043d\u043e\u0432\u044b\u0439', tone: 'blue' },
  { value: '1', label: '\u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0430 \u043f\u0440\u0435\u0434\u043e\u043f\u043b\u0430\u0442\u0430', tone: 'green' },
  { value: '2', label: 'Avito \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0430', tone: 'amber' },
  { value: '3', label: 'Ozon', tone: 'slate' },
  { value: '4', label: '\u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d', tone: 'green' },
  { value: '5', label: '\u0433\u043e\u0442\u043e\u0432 \u043a \u0432\u044b\u0434\u0430\u0447\u0435', tone: 'blue' },
  { value: '6', label: '\u043e\u0442\u043c\u0435\u043d\u0435\u043d', tone: 'red' },
  { value: '7', label: '\u043e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u0440\u0435\u0434\u043e\u043f\u043b\u0430\u0442\u044b', tone: 'amber' },
]

export const STATUS_MAP = Object.fromEntries(
  STATUS_OPTIONS.map((status) => [status.value, status]),
)

export const INITIAL_CUSTOMER_FORM = () => ({
  name: '',
  surname: '',
  phone: '',
  address: '',
  note: '',
  status: '0',
  shipping_date: new Date().toISOString().split('T')[0],
})

export const NAV_ITEMS = [
  { path: '/', label: '\u041a\u0430\u0442\u0430\u043b\u043e\u0433', shortLabel: '\u041a\u0430\u0442\u0430\u043b\u043e\u0433', icon: 'OP' },
  {
    path: '/quick-order',
    label: '\u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u0437\u0430\u043a\u0430\u0437',
    shortLabel: '\u0411\u044b\u0441\u0442\u0440\u043e',
    icon: 'QO',
  },
  { path: '/orders', label: '\u0417\u0430\u043a\u0430\u0437\u044b', shortLabel: '\u0417\u0430\u043a\u0430\u0437\u044b', icon: 'OR' },
  { path: '/admin', label: '\u0410\u0434\u043c\u0438\u043d', shortLabel: '\u0410\u0434\u043c\u0438\u043d', icon: 'AD' },
]
