import { Link } from 'react-router-dom'
import { dateRu, money, relativeDay, todayIso } from '../lib/format'
import StatusSelect from './StatusSelect'

// Компактная строка заказа для сводки и карточки клиента.
export default function OrderRow({ order, onChanged, showCustomer = true }) {
  const overdue = order.shipping_date && order.shipping_date < todayIso()
    && !['done', 'cancelled'].includes(order.status_role)

  return (
    <div className="crm-row">
      <div className="crm-row__main">
        <div className="crm-row__title">
          <Link to={`/orders?focus=${order.id}`} className="crm-link">
            Заказ №{order.id}
          </Link>
          {showCustomer ? (
            <>
              {' · '}
              <Link to={`/customers/${order.customer_id}`} className="crm-link crm-link--plain">
                {order.customer_full_name || 'без имени'}
              </Link>
            </>
          ) : null}
        </div>
        <div className="crm-row__meta">{order.items_text || 'без позиций'}</div>
        {order.note ? <div className="crm-row__meta crm-row__note">{order.note}</div> : null}
      </div>
      <div className="crm-row__side">
        <div className="crm-row__sum">{money(order.total_price)}</div>
        <div className={overdue ? 'crm-row__date crm-row__date--overdue' : 'crm-row__date'}>
          {dateRu(order.shipping_date)} · {relativeDay(order.shipping_date)}
        </div>
        <StatusSelect orderId={order.id} status={order.status} onChanged={onChanged} compact />
      </div>
    </div>
  )
}
