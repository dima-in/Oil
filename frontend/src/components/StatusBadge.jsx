import { statusTone, useStatuses } from '../lib/statuses'

export default function StatusBadge({ status, name, role }) {
  const statuses = useStatuses()
  const known = statuses.find((item) => String(item.id) === String(status))
  const label = name || known?.name || String(status)
  const tone = statusTone(role !== undefined ? role : known?.role)

  return <span className={`status-badge status-badge--${tone}`}>{label}</span>
}
