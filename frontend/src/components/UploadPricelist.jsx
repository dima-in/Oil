import { useState } from 'react'

const API_BASE = '/api'

export default function UploadPricelist() {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleUpload = async (e) => {
    e.preventDefault()
    setUploading(true)
    setError(null)
    setResult(null)

    const file = e.target.pdf_file.files[0]
    if (!file) {
      setError('Выберите файл')
      setUploading(false)
      return
    }

    const formData = new FormData()
    formData.append('pdf_file', file)

    try {
      const response = await fetch(`${API_BASE}/admin/upload-pricelist`, {
        method: 'POST',
        headers: {
          'Authorization': 'Basic ' + btoa('oilpress:MarshallJCM800')
        },
        body: formData
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Ошибка загрузки')
      }

      setResult('Прайс-лист успешно загружен!')
    } catch (error) {
      setError(error.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-md">
      <h2 className="text-xl font-bold mb-4">📤 Загрузка прайс-листа</h2>

      <form onSubmit={handleUpload} className="space-y-4">
        <div className="p-8 border-2 border-dashed border-white/20 rounded-xl text-center hover:border-white/30 transition-colors">
          <div className="text-4xl mb-2">📄</div>
          <div className="text-sm text-gray-400 mb-4">
            Выберите PDF или CSV файл
          </div>
          <input
            type="file"
            name="pdf_file"
            accept=".pdf,.csv"
            className="block w-full text-sm text-gray-400
              file:mr-4 file:py-2 file:px-4
              file:rounded-lg file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-500/20 file:text-blue-400
              hover:file:bg-blue-500/30 transition-colors"
            required
          />
        </div>

        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
            ❌ {error}
          </div>
        )}

        {result && (
          <div className="p-4 bg-green-500/20 border border-green-500/50 rounded-lg text-green-400 text-sm">
            ✅ {result}
          </div>
        )}

        <button
          type="submit"
          disabled={uploading}
          className="ios-button w-full disabled:opacity-50"
        >
          {uploading ? '⏳ Загрузка...' : '📤 Загрузить прайс-лист'}
        </button>
      </form>

      <div className="mt-6 p-4 bg-white/5 rounded-lg">
        <h3 className="text-sm font-semibold mb-2 text-gray-400">📖 Инструкция:</h3>
        <ol className="text-sm text-gray-300 space-y-1 list-decimal list-inside">
          <li>Экспортируйте прайс-лист в PDF или CSV</li>
          <li>Загрузите файл через форму выше</li>
          <li>Система автоматически обработает файл</li>
        </ol>
        <p className="text-xs text-orange-400 mt-3">
          ⚠️ Внимание! Загрузка нового прайс-листа очистит текущие данные.
        </p>
      </div>
    </div>
  )
}
