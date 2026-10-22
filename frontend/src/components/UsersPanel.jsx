import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

const EMPTY_USER = { username: '', full_name: '', password: '', role: 'manager' }

function PasswordForm() {
  const [form, setForm] = useState({ current: '', next: '' })
  const [notice, setNotice] = useState(null)

  const save = async (event) => {
    event.preventDefault()
    setNotice(null)
    try {
      await api.changePassword(form.current, form.next)
      setForm({ current: '', next: '' })
      setNotice({ type: 'success', text: 'Пароль изменён' })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    }
  }

  return (
    <form className="inline-form" onSubmit={save}>
      <input className="ios-input" type="password" placeholder="Текущий пароль" value={form.current}
        onChange={(event) => setForm((prev) => ({ ...prev, current: event.target.value }))} autoComplete="current-password" />
      <input className="ios-input" type="password" placeholder="Новый пароль (от 8 символов)" value={form.next}
        onChange={(event) => setForm((prev) => ({ ...prev, next: event.target.value }))} autoComplete="new-password" />
      <button type="submit" className="ios-button primary">Сменить</button>
      {notice ? <div className={`notice notice--${notice.type} inline-form__notice`}>{notice.text}</div> : null}
    </form>
  )
}

export default function UsersPanel({ user }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(EMPTY_USER)
  const [error, setError] = useState('')
  const isAdmin = user.role === 'admin'

  const load = useCallback(async () => {
    if (!isAdmin) return
    try {
      const rows = await api.listUsers()
      setUsers(rows)
    } catch (err) {
      setError(err.message)
    }
  }, [isAdmin])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии экрана
    load()
  }, [load])

  const create = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await api.createUser(form)
      setForm(EMPTY_USER)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const update = async (target, patch) => {
    try {
      await api.updateUser(target.id, patch)
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div className="page-stack page-stack--compact">
      <div className="section-head">
        <div>
          <h3 className="section-head__title">Мой пароль</h3>
          <p className="section-head__text">Вы вошли как {user.username}.</p>
        </div>
      </div>
      <PasswordForm />

      {isAdmin ? (
        <>
          <div className="section-head">
            <div>
              <h3 className="section-head__title">Сотрудники</h3>
              <p className="section-head__text">
                У каждого свой вход. Менеджер работает с заказами и клиентами, администратор ещё меняет настройки и
                пользователей.
              </p>
            </div>
          </div>
          <form className="inline-form" onSubmit={create}>
            <input className="ios-input" placeholder="Логин" value={form.username}
              onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))} />
            <input className="ios-input" placeholder="Имя" value={form.full_name}
              onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))} />
            <input className="ios-input" type="password" placeholder="Пароль (от 8)" value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))} autoComplete="new-password" />
            <select className="ios-input" value={form.role}
              onChange={(event) => setForm((prev) => ({ ...prev, role: event.target.value }))}>
              <option value="manager">менеджер</option>
              <option value="admin">администратор</option>
            </select>
            <button type="submit" className="ios-button primary">Добавить</button>
          </form>
          {error ? <div className="notice notice--error">{error}</div> : null}
          <div className="table-wrap">
            <table className="price-table crm-table">
              <thead>
                <tr>
                  <th>Логин</th>
                  <th>Имя</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((row) => (
                  <tr key={row.id}>
                    <td>{row.username}</td>
                    <td>{row.full_name || '—'}</td>
                    <td>{row.role === 'admin' ? 'администратор' : 'менеджер'}</td>
                    <td>{row.is_active ? 'активен' : <span className="muted">отключён</span>}</td>
                    <td className="table-actions">
                      {row.id !== user.id ? (
                        <>
                          <button type="button" className="link-button"
                            onClick={() => update(row, { role: row.role === 'admin' ? 'manager' : 'admin' })}>
                            {row.role === 'admin' ? 'сделать менеджером' : 'сделать админом'}
                          </button>
                          <button type="button" className={row.is_active ? 'link-danger' : 'link-button'}
                            onClick={() => update(row, { is_active: !row.is_active })}>
                            {row.is_active ? 'отключить' : 'включить'}
                          </button>
                        </>
                      ) : (
                        <span className="muted">это вы</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
