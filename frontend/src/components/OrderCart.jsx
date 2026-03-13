export default function OrderCart({ items, totalPrice, onCheckout }) {
  if (items.length === 0) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 glass border-t border-white/10 p-4 z-40">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div>
          <div className="text-sm text-gray-400">В корзине</div>
          <div className="text-xl font-bold">{totalPrice.toLocaleString()} ₽</div>
        </div>
        <button onClick={onCheckout} className="ios-button success">
          Оформить заказ
        </button>
      </div>
    </div>
  )
}
