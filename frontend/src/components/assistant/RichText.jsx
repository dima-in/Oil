import { Fragment } from 'react'
import { Link } from 'react-router-dom'

// Небольшой разбор ответа модели без dangerouslySetInnerHTML: **жирный**, списки,
// абзацы и ссылки «заказ №12» / «клиент №5» прямо в карточки CRM.
const TOKEN_RE = /(\*\*[^*]+\*\*|(?:заказ|заказа|заказу|заказе)\s*№\s*\d+|клиент(?:а|у|ом|е)?\s*№\s*\d+|задач[аиу]\s*№\s*\d+)/gi

function inline(text, keyPrefix) {
  const parts = text.split(TOKEN_RE)
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`
    if (!part) return null
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={key}>{part.slice(2, -2)}</strong>
    }
    const id = (part.match(/№\s*(\d+)/) || [])[1]
    if (id && /^заказ/i.test(part)) {
      return (
        <Link key={key} to={`/orders?focus=${id}`} className="crm-link">
          {part}
        </Link>
      )
    }
    if (id && /^клиент/i.test(part)) {
      return (
        <Link key={key} to={`/customers/${id}`} className="crm-link">
          {part}
        </Link>
      )
    }
    if (id && /^задач/i.test(part)) {
      return (
        <Link key={key} to="/tasks" className="crm-link">
          {part}
        </Link>
      )
    }
    return <Fragment key={key}>{part}</Fragment>
  })
}

export default function RichText({ text }) {
  const blocks = []
  let list = null

  String(text || '')
    .split('\n')
    .forEach((rawLine, index) => {
      const line = rawLine.trimEnd()
      const bullet = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/)
      if (bullet) {
        if (!list) {
          list = { ordered: /^\s*\d/.test(line), items: [] }
          blocks.push(list)
        }
        list.items.push(bullet[1])
        return
      }
      list = null
      if (line.trim()) {
        const heading = line.match(/^#{1,4}\s+(.*)$/)
        blocks.push({ text: heading ? heading[1] : line, heading: Boolean(heading), index })
      }
    })

  return (
    <div className="rich-text">
      {blocks.map((block, index) => {
        if (block.items) {
          const Tag = block.ordered ? 'ol' : 'ul'
          return (
            <Tag key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{inline(item, `${index}-${itemIndex}`)}</li>
              ))}
            </Tag>
          )
        }
        return block.heading ? (
          <h4 key={index}>{inline(block.text, String(index))}</h4>
        ) : (
          <p key={index}>{inline(block.text, String(index))}</p>
        )
      })}
    </div>
  )
}
