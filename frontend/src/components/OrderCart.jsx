export default function OrderCart({ items, totalPrice, onCheckout }) {
  if (items.length === 0) {
    return null
  }

  return (
    <div className="cart-bar">
      <div className="app-shell cart-bar__inner">
        <div>
          <div className="cart-bar__label">В корзине</div>
          <div className="cart-bar__total">{totalPrice.toLocaleString('ru-RU')} ₽</div>
        </div>
        <button onClick={onCheckout} className="ios-button success">
          Оформить заказ
        </button>
      </div>
    </div>
  )
}
