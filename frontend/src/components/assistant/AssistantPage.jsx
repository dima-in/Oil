import AssistantChat from './AssistantChat'

const CAPABILITIES = [
  ['Отвечает по базе', 'Выручка, прибыль, топ клиентов и масел, сравнение периодов — пишет SQL сам, только на чтение.'],
  ['Заказ из текста или голосом', 'Вставьте сообщение из Avito/WhatsApp или надиктуйте — найдёт клиента, сверит с прайсом, соберёт заказ.'],
  ['Планирует прессы', 'Раскладывает закладки по прессам и дням под сроки отгрузки, видит, что не успевает.'],
  ['Ведёт дела', 'Задачи, напоминания, заметки о звонках, расходы и записи о партиях — черновиком на подтверждение.'],
]

export default function AssistantPage() {
  return (
    <div className="assistant-page">
      <AssistantChat variant="page" />
      <aside className="assistant-page__aside">
        <h2 className="crm-block__title">Что умеет помощник</h2>
        {CAPABILITIES.map(([title, text]) => (
          <div key={title} className="capability">
            <div className="capability__title">{title}</div>
            <div className="capability__text">{text}</div>
          </div>
        ))}
        <div className="capability capability--note">
          Ничего не меняет без вашего «Подтвердить» и не умеет удалять. Служебные таблицы (пароли) ему недоступны.
        </div>
      </aside>
    </div>
  )
}
