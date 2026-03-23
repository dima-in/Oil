import { STATUS_MAP } from '../lib/constants'

export default function StatusBadge({ status }) {
  const config = STATUS_MAP[String(status)] || {
    label: String(status),
    tone: 'slate',
  }

  return (
    <span className={`status-badge status-badge--${config.tone}`}>
      {config.label}
    </span>
  )
}
