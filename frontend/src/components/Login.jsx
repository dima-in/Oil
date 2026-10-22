import { useState } from 'react'
import { api } from '../lib/api'
import { saveSession } from '../lib/auth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { token, user } = await api.login(username.trim(), password)
      saveSession(token, user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-card__brand">OilPress</div>
        <h1 className="login-card__title">Вход в CRM</h1>
        <p className="login-card__text">Заказы, клиенты, производство и ИИ-помощник.</p>
        <label className="field">
          <span className="field__label">Логин</span>
          <input
            className="ios-input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </label>
        <label className="field">
          <span className="field__label">Пароль</span>
          <input
            className="ios-input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error ? <div className="notice notice--error">{error}</div> : null}
        <button type="submit" className="ios-button primary" disabled={loading}>
          {loading ? 'Входим…' : 'Войти'}
        </button>
      </form>
    </div>
  )
}
