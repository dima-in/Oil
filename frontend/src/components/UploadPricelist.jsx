import { useState } from 'react'
import { api } from '../lib/api'

export default function UploadPricelist() {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  const handleUpload = async (event) => {
    event.preventDefault()
    setUploading(true)
    setError('')
    setResult('')

    const file = event.target.pdf_file.files[0]

    if (!file) {
      setError('Выберите файл.')
      setUploading(false)
      return
    }

    const formData = new FormData()
    formData.append('pdf_file', file)

    try {
      const response = await api.uploadPricelist(formData)
      setResult(response?.message || 'Прайс-лист успешно загружен.')
    } catch (uploadError) {
      setError(uploadError.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page-stack page-stack--compact">
      <div>
        <h2 className="section-head__title">Загрузка прайс-листа</h2>
        <p className="section-head__text">Поддерживается PDF или CSV. Текущий список будет очищен перед импортом.</p>
      </div>

      <form onSubmit={handleUpload} className="form-stack">
        <label className="upload-dropzone">
          <span className="upload-dropzone__title">Выберите файл</span>
          <span className="upload-dropzone__text">PDF или CSV для обновления ассортимента.</span>
          <input type="file" name="pdf_file" accept=".pdf,.csv" className="upload-dropzone__input" required />
        </label>

        {error ? <div className="notice notice--error">{error}</div> : null}
        {result ? <div className="notice notice--success">{result}</div> : null}

        <button type="submit" disabled={uploading} className="ios-button">
          {uploading ? 'Загрузка...' : 'Загрузить прайс-лист'}
        </button>
      </form>
    </div>
  )
}
