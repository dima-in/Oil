import { useEffect, useMemo, useState } from 'react'
import OrderCart from './OrderCart'
import PageHeader from './PageHeader'
import { api } from '../lib/api'
import { buildCartItems, buildProductIndex, calculateCartTotal, groupCatalogItems } from '../lib/catalog'
import { INITIAL_CUSTOMER_FORM, STATUS_OPTIONS } from '../lib/constants'

const PRODUCT_IMAGE_ALIASES = {
  'кунжут нешлифованный': 'кунжут не шлифованый',
}

function getProductImageSrc(productName) {
  const imageName = PRODUCT_IMAGE_ALIASES[productName] || productName
  return `/static/images/${encodeURIComponent(imageName)}.jpg`
}

function ProductCard({ group, getQuantity, onQuantityChange }) {
  return (
    <article className="product-card">
      <div className="product-card__body">
        <div className="product-card__head">
          <div className="product-card__media">
            <img
              src={getProductImageSrc(group.name)}
              alt={group.name}
              className="product-card__image"
              onError={(event) => {
                event.currentTarget.style.display = 'none'
                event.currentTarget.parentElement.dataset.fallback = group.name.slice(0, 2).toUpperCase()
              }}
            />
          </div>

          <div className="product-card__info">
            <h3 className="product-card__title" title={group.name}>
              {group.name}
            </h3>
            <div className="product-card__subtitle">
              {group.items.length} {group.items.length === 1 ? 'вариант' : 'варианта'}
            </div>
          </div>
        </div>

        <div className="product-card__variants">
          {group.items.map((item) => {
            const quantity = getQuantity(item.oil_name, item.volume)

            return (
              <div key={`${item.oil_name}_${item.volume}`} className="product-variant">
                <div className="product-variant__details">
                  <div className="product-variant__volume">{item.volume} мл</div>
                  <div className="product-variant__price">{item.price} ₽</div>
                </div>

                {quantity === 0 ? (
                  <button
                    type="button"
                    onClick={() => onQuantityChange(item.oil_name, item.volume, 1)}
                    className="add-button"
                    aria-label={`Добавить ${group.name} ${item.volume} мл`}
                  >
                    Добавить
                  </button>
                ) : (
                  <div className="quantity-stepper">
                    <button
                      type="button"
                      onClick={() => onQuantityChange(item.oil_name, item.volume, quantity - 1)}
                      className="quantity-stepper__button"
                      aria-label={`Уменьшить ${group.name} ${item.volume} мл`}
                    >
                      -
                    </button>
                    <input
                      type="number"
                      min="0"
                      value={quantity}
                      onChange={(event) =>
                        onQuantityChange(
                          item.oil_name,
                          item.volume,
                          Math.max(0, Number(event.target.value) || 0),
                        )
                      }
                      className="quantity-stepper__input"
                      aria-label={`Количество ${group.name} ${item.volume} мл`}
                    />
                    <button
                      type="button"
                      onClick={() => onQuantityChange(item.oil_name, item.volume, quantity + 1)}
                      className="quantity-stepper__button quantity-stepper__button--primary"
                      aria-label={`Увеличить ${group.name} ${item.volume} мл`}
                    >
                      +
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </article>
  )
}

function CheckoutModal({
  cartItems,
  customerForm,
  onClose,
  onFieldChange,
  onSubmit,
  productsByKey,
  submitting,
  totalPrice,
}) {
  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <PageHeader
          eyebrow="Оформление"
          title="Подтверждение заказа"
          description="Проверьте корзину и заполните данные покупателя."
        />

        <section className="order-summary">
          {cartItems.map((item) => {
            const product = productsByKey[`${item.oilName}_${item.volume}`]
            const lineTotal = (product?.price || 0) * item.quantity

            return (
              <div key={`${item.oilName}_${item.volume}`} className="order-summary__row">
                <span>
                  {item.oilName} ({item.volume} мл) x {item.quantity}
                </span>
                <span>{lineTotal.toLocaleString('ru-RU')} ₽</span>
              </div>
            )
          })}

          <div className="order-summary__total">
            <span>Итого</span>
            <span>{totalPrice.toLocaleString('ru-RU')} ₽</span>
          </div>
        </section>

        <form onSubmit={onSubmit} className="form-stack">
          <input
            type="text"
            placeholder="Имя"
            value={customerForm.name}
            onChange={(event) => onFieldChange('name', event.target.value)}
            className="ios-input"
            required
          />
          <input
            type="text"
            placeholder="Фамилия"
            value={customerForm.surname}
            onChange={(event) => onFieldChange('surname', event.target.value)}
            className="ios-input"
            required
          />
          <input
            type="tel"
            placeholder="Телефон"
            value={customerForm.phone}
            onChange={(event) => onFieldChange('phone', event.target.value)}
            className="ios-input"
            required
          />
          <input
            type="text"
            placeholder="Адрес"
            value={customerForm.address}
            onChange={(event) => onFieldChange('address', event.target.value)}
            className="ios-input"
            required
          />
          <select
            value={customerForm.status}
            onChange={(event) => onFieldChange('status', event.target.value)}
            className="ios-input"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={customerForm.shipping_date}
            onChange={(event) => onFieldChange('shipping_date', event.target.value)}
            className="ios-input"
            required
          />

          <div className="modal-card__actions">
            <button type="button" onClick={onClose} className="ios-button secondary">
              Отмена
            </button>
            <button type="submit" disabled={submitting} className="ios-button success">
              {submitting ? 'Отправка...' : 'Подтвердить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Catalog() {
  const [products, setProducts] = useState([])
  const [quantities, setQuantities] = useState({})
  const [customerForm, setCustomerForm] = useState(INITIAL_CUSTOMER_FORM)
  const [loading, setLoading] = useState(true)
  const [showCustomerForm, setShowCustomerForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function fetchProducts() {
      try {
        const data = await api.getCatalog()
        if (!cancelled) {
          setProducts(groupCatalogItems(data))
        }
      } catch (error) {
        console.error('Error fetching products:', error)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchProducts()

    return () => {
      cancelled = true
    }
  }, [])

  const productsByKey = useMemo(() => buildProductIndex(products), [products])
  const cartItems = useMemo(() => buildCartItems(quantities), [quantities])
  const totalPrice = useMemo(
    () => calculateCartTotal(cartItems, productsByKey),
    [cartItems, productsByKey],
  )
  const totalCount = useMemo(
    () => cartItems.reduce((sum, item) => sum + item.quantity, 0),
    [cartItems],
  )

  const updateQuantity = (oilName, volume, quantity) => {
    const key = `${oilName}_${volume}`

    setQuantities((previous) => {
      const next = { ...previous }

      if (quantity > 0) {
        next[key] = { oilName, volume, quantity }
      } else {
        delete next[key]
      }

      return next
    })
  }

  const getQuantity = (oilName, volume) => quantities[`${oilName}_${volume}`]?.quantity || 0

  const handleFieldChange = (field, value) => {
    setCustomerForm((previous) => ({ ...previous, [field]: value }))
  }

  const resetOrderState = () => {
    setQuantities({})
    setShowCustomerForm(false)
    setCustomerForm(INITIAL_CUSTOMER_FORM())
  }

  const handleSubmitOrder = async (event) => {
    event.preventDefault()
    setSubmitting(true)

    const orderData = {
      ...customerForm,
      items: cartItems.map((item) => {
        const product = productsByKey[`${item.oilName}_${item.volume}`]
        return {
          oil_name: item.oilName,
          volume: item.volume,
          count: item.quantity,
          price: product?.price || 0,
        }
      }),
    }

    try {
      await api.createOrder(orderData)
      alert('Заказ успешно создан.')
      resetOrderState()
    } catch (error) {
      alert(`Ошибка при создании заказа: ${error.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <div className="state-panel">Загрузка каталога...</div>
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Витрина"
        title="Каталог масел"
        description="Соберите корзину и сразу оформите заказ на нужные объёмы."
      />

      <section className="product-grid">
        {products.map((group) => (
          <ProductCard
            key={group.name}
            group={group}
            getQuantity={getQuantity}
            onQuantityChange={updateQuantity}
          />
        ))}
      </section>

      <OrderCart
        items={cartItems}
        totalPrice={totalPrice}
        onCheckout={() => setShowCustomerForm(true)}
      />

      {showCustomerForm ? (
        <CheckoutModal
          cartItems={cartItems}
          customerForm={customerForm}
          onClose={() => setShowCustomerForm(false)}
          onFieldChange={handleFieldChange}
          onSubmit={handleSubmitOrder}
          productsByKey={productsByKey}
          submitting={submitting}
          totalPrice={totalPrice}
        />
      ) : null}

      {cartItems.length > 0 ? <div className="cart-bar__spacer" aria-hidden="true" /> : null}
      {totalCount > 0 ? <div className="page-hint">Выбрано позиций: {totalCount}</div> : null}
    </div>
  )
}
