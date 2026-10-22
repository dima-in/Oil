import { useCallback, useEffect, useRef, useState } from 'react'

const Recognition = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

const ERRORS = {
  'not-allowed': 'Нет доступа к микрофону. Разрешите его в браузере (нужен HTTPS).',
  'service-not-allowed': 'Браузер запретил распознавание речи на этой странице (нужен HTTPS).',
  'no-speech': 'Ничего не услышал — попробуйте ещё раз.',
  network: 'Сервис распознавания речи недоступен — проверьте интернет.',
  'audio-capture': 'Микрофон не найден.',
}

// Диктовка через Web Speech API. onText получает распознанный текст по мере речи:
// (окончательный текст, черновой хвост).
export function useDictation(onText) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const recognitionRef = useRef(null)
  const onTextRef = useRef(onText)
  useEffect(() => {
    onTextRef.current = onText
  }, [onText])

  const supported = Boolean(Recognition) && (window.isSecureContext ?? true)
  const reason = !Recognition
    ? 'Этот браузер не умеет распознавать речь — используйте Chrome, Edge или Safari, либо голосовой ввод клавиатуры телефона.'
    : !supported
      ? 'Микрофон в браузере работает только по HTTPS. Пока можно диктовать голосовым вводом клавиатуры телефона.'
      : ''

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  const start = useCallback(() => {
    if (!supported) {
      setError(reason)
      return
    }
    setError('')
    const recognition = new Recognition()
    recognition.lang = 'ru-RU'
    recognition.continuous = true
    recognition.interimResults = true
    let finalText = ''
    recognition.onresult = (event) => {
      let interim = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) finalText += `${result[0].transcript} `
        else interim += result[0].transcript
      }
      onTextRef.current?.(finalText.trim(), interim.trim())
    }
    recognition.onerror = (event) => setError(ERRORS[event.error] || `Ошибка распознавания: ${event.error}`)
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }, [reason, supported])

  useEffect(() => () => recognitionRef.current?.abort(), [])

  return { listening, start, stop, error, supported, reason }
}
