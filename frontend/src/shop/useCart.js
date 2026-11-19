import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'oil-shop-cart'

function readStored() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? parsed.filter((line) => line?.oil_name && line?.volume && line?.count > 0) : []
  } catch {
    return []
  }
}

export const lineKey = (line) => `${line.oil_name}|${line.volume}`

// Корзина хранит только масло, объём и количество; цены всегда берутся из свежего каталога.
export default function useCart() {
  const [lines, setLines] = useState(readStored)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(lines))
    } catch {
      /* приватный режим: корзина живёт до перезагрузки */
    }
  }, [lines])

  const add = useCallback((oilName, volume, count = 1) => {
    setLines((prev) => {
      const key = lineKey({ oil_name: oilName, volume })
      const existing = prev.find((line) => lineKey(line) === key)
      if (existing) {
        return prev.map((line) => (line === existing ? { ...line, count: Math.min(line.count + count, 50) } : line))
      }
      return [...prev, { oil_name: oilName, volume, count: Math.min(count, 50) }]
    })
  }, [])

  const setCount = useCallback((key, count) => {
    setLines((prev) =>
      count <= 0
        ? prev.filter((line) => lineKey(line) !== key)
        : prev.map((line) => (lineKey(line) === key ? { ...line, count: Math.min(count, 50) } : line)),
    )
  }, [])

  const clear = useCallback(() => setLines([]), [])

  return { lines, add, setCount, clear }
}
