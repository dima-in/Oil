import { useState, useEffect } from 'react'
import OrderCart from './OrderCart'

const API_BASE = '/api'

export default function Catalog() {
  const [products, setProducts] = useState([])
  const [quantities, setQuantities] = useState({})
  const [loading, setLoading] = useState(true)
  const [customerForm, setCustomerForm] = useState({
    name: '',
    surname: '',
    phone: '',
    address: '',
    status: '0',
    shipping_date: new Date().toISOString().split('T')[0]
  })
  const [showCustomerForm, setShowCustomerForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    try {
      const response = await fetch(`${API_BASE}/catalog`)
      if (!response.ok) throw new Error('Failed to fetch')
      const data = await response.json()
      setProducts(data)
      
      // Group products by oil name
      const grouped = {}
      data.forEach(item => {
        if (!grouped[item.oil_name]) {
          grouped[item.oil_name] = []
        }
        grouped[item.oil_name].push(item)
      })
      setProducts(Object.entries(grouped).map(([name, items]) => ({ name, items })))
    } catch (error) {
      console.error('Error fetching products:', error)
    } finally {
      setLoading(false)
    }
  }

  const updateQuantity = (oilName, volume, quantity) => {
    const key = `${oilName}_${volume}`
    setQuantities(prev => {
      const newQuantities = { ...prev }
      if (quantity > 0) {
        newQuantities[key] = { oilName, volume, quantity }
      } else {
        delete newQuantities[key]
      }
      return newQuantities
    })
  }

  const getQuantity = (oilName, volume) => {
    const key = `${oilName}_${volume}`
    return quantities[key]?.quantity || 0
  }

  const cartItems = Object.values(quantities)
  const totalPrice = cartItems.reduce((sum, item) => {
    const product = products.flatMap(g => g.items).find(p => p.oil_name === item.oilName && p.volume === item.volume)
    return sum + (product?.price || 0) * item.quantity
  }, 0)

  const handleSubmitOrder = async (e) => {
    e.preventDefault()
    setSubmitting(true)

    const orderData = {
      ...customerForm,
      items: cartItems.map(item => {
        const product = products.flatMap(g => g.items).find(p => p.oil_name === item.oilName && p.volume === item.volume)
        return {
          oil_name: item.oilName,
          volume: item.volume,
          count: item.quantity,
          price: product?.price || 0
        }
      })
    }

    try {
      const response = await fetch(`${API_BASE}/order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        },
        body: JSON.stringify(orderData)
      })

      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || 'Failed to create order')
      }

      alert('Заказ успешно создан!')
      setQuantities({})
      setShowCustomerForm(false)
      setCustomerForm({
        name: '',
        surname: '',
        phone: '',
        address: '',
        status: '0',
        shipping_date: new Date().toISOString().split('T')[0]
      })
    } catch (error) {
      alert('Ошибка при создании заказа: ' + error.message)
    } finally {
      setSubmitting(false)
    }
  }

  const statusOptions = [
    { value: '0', label: 'новый' },
    { value: '1', label: 'получена предоплата' },
    { value: '2', label: 'Avito доставка' },
    { value: '3', label: 'Ozon' },
    { value: '4', label: 'завершен' },
    { value: '5', label: 'готов к выдаче' },
    { value: '6', label: 'отменен' },
    { value: '7', label: 'ожидает предоплаты' }
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <h1 className="text-3xl font-bold mb-6 bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent">
        Каталог масел
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {products.map((group) => (
          <div key={group.name} className="ios-card animate-fade-in">
            <div className="mb-4">
              <div className="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center text-4xl mb-2">
                🫒
              </div>
              <h3 className="text-lg font-semibold text-center">{group.name}</h3>
            </div>

            <div className="space-y-2">
              {group.items.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 transition-colors">
                  <div>
                    <div className="text-sm font-medium">{item.volume} мл</div>
                    <div className="text-xs text-gray-400">{item.price} ₽/л</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => updateQuantity(item.oil_name, item.volume, getQuantity(item.oil_name, item.volume) - 1)}
                      className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 transition-colors flex items-center justify-center"
                    >
                      −
                    </button>
                    <span className="w-8 text-center font-medium">
                      {getQuantity(item.oil_name, item.volume)}
                    </span>
                    <button
                      onClick={() => updateQuantity(item.oil_name, item.volume, getQuantity(item.oil_name, item.volume) + 1)}
                      className="w-8 h-8 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 transition-colors flex items-center justify-center text-blue-400"
                    >
                      +
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Cart Summary */}
      {cartItems.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 glass border-t border-white/10 p-4 safe-area-pb">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-400">В корзине</div>
              <div className="text-xl font-bold">{totalPrice.toLocaleString()} ₽</div>
            </div>
            <button
              onClick={() => setShowCustomerForm(true)}
              className="ios-button success"
            >
              Оформить заказ ({cartItems.reduce((sum, i) => sum + i.quantity, 0)} шт)
            </button>
          </div>
        </div>
      )}

      {/* Customer Form Modal */}
      {showCustomerForm && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="ios-card w-full max-w-md max-h-[90vh] overflow-y-auto animate-fade-in">
            <h2 className="text-xl font-bold mb-4">Оформление заказа</h2>
            
            <div className="mb-4 p-3 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-2">Товары:</div>
              {cartItems.map((item, idx) => {
                const product = products.flatMap(g => g.items).find(p => p.oil_name === item.oilName && p.volume === item.volume)
                return (
                  <div key={idx} className="flex justify-between text-sm py-1 border-b border-white/5 last:border-0">
                    <span>{item.oilName} ({item.volume}мл) × {item.quantity}</span>
                    <span>{((product?.price || 0) * item.quantity).toLocaleString()} ₽</span>
                  </div>
                )
              })}
              <div className="flex justify-between font-bold mt-2 pt-2 border-t border-white/10">
                <span>Итого:</span>
                <span className="text-green-400">{totalPrice.toLocaleString()} ₽</span>
              </div>
            </div>

            <form onSubmit={handleSubmitOrder} className="space-y-3">
              <input
                type="text"
                placeholder="Имя"
                value={customerForm.name}
                onChange={(e) => setCustomerForm({...customerForm, name: e.target.value})}
                className="ios-input w-full"
                required
              />
              <input
                type="text"
                placeholder="Фамилия"
                value={customerForm.surname}
                onChange={(e) => setCustomerForm({...customerForm, surname: e.target.value})}
                className="ios-input w-full"
                required
              />
              <input
                type="tel"
                placeholder="Телефон"
                value={customerForm.phone}
                onChange={(e) => setCustomerForm({...customerForm, phone: e.target.value})}
                className="ios-input w-full"
                required
              />
              <input
                type="text"
                placeholder="Адрес"
                value={customerForm.address}
                onChange={(e) => setCustomerForm({...customerForm, address: e.target.value})}
                className="ios-input w-full"
                required
              />
              <select
                value={customerForm.status}
                onChange={(e) => setCustomerForm({...customerForm, status: e.target.value})}
                className="ios-input w-full"
              >
                {statusOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <input
                type="date"
                value={customerForm.shipping_date}
                onChange={(e) => setCustomerForm({...customerForm, shipping_date: e.target.value})}
                className="ios-input w-full"
                required
              />

              <div className="flex gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCustomerForm(false)}
                  className="ios-button secondary flex-1"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="ios-button success flex-1 disabled:opacity-50"
                >
                  {submitting ? 'Отправка...' : 'Подтвердить'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Spacer for fixed cart */}
      {cartItems.length > 0 && <div className="h-20"></div>}
    </div>
  )
}
