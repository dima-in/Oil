const TOKEN_KEY = 'oilpress-token'
const USER_KEY = 'oilpress-user'
export const AUTH_EVENT = 'oilpress:auth'

// Запасное хранилище на случай запрета localStorage (приватный режим).
const memory = { token: null, user: null }

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || memory.token
  } catch {
    return memory.token
  }
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : memory.user
  } catch {
    return memory.user
  }
}

export function saveSession(token, user) {
  memory.token = token
  memory.user = user
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    /* private mode: keep the session in memory */
  }
  window.dispatchEvent(new Event(AUTH_EVENT))
}

export function clearSession() {
  memory.token = null
  memory.user = null
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(AUTH_EVENT))
}
