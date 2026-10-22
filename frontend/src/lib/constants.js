export const API_BASE = '/api'

export const ORDER_TEMPLATE = 'Оформи заказ по заявке клиента:\n'

export const INITIAL_CUSTOMER_FORM = () => ({
  name: '',
  surname: '',
  phone: '',
  address: '',
  note: '',
  status: '0',
  shipping_date: new Date().toISOString().split('T')[0],
})

export const NAV_SECTIONS = [
  {
    title: 'Работа',
    items: [
      { path: '/', label: 'Сегодня', icon: 'home' },
      { path: '/assistant', label: 'ИИ-помощник', icon: 'spark' },
      { path: '/orders', label: 'Заказы', icon: 'box' },
      { path: '/quick-order', label: 'Запись заказа', icon: 'calendar' },
      { path: '/customers', label: 'Клиенты', icon: 'users' },
      { path: '/tasks', label: 'Задачи', icon: 'check' },
    ],
  },
  {
    title: 'Производство',
    items: [
      { path: '/production', label: 'Остатки и отжим', icon: 'drop' },
      { path: '/catalog', label: 'Каталог', icon: 'grid' },
      { path: '/admin', label: 'Управление', icon: 'gear' },
    ],
  },
]
