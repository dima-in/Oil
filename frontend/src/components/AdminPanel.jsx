import { useState, useEffect } from 'react'
import PricelistManager from './PricelistManager'
import UploadPricelist from './UploadPricelist'

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('pricelist')

  return (
    <div className="animate-fade-in">
      <h1 className="text-3xl font-bold mb-6 bg-gradient-to-r from-purple-400 to-purple-600 bg-clip-text text-transparent">
        ⚙️ Админ-панель
      </h1>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('pricelist')}
          className={`px-4 py-2 rounded-lg font-medium transition-all ${
            activeTab === 'pricelist'
              ? 'bg-purple-500/20 text-purple-400'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          📊 Прайс-лист
        </button>
        <button
          onClick={() => setActiveTab('upload')}
          className={`px-4 py-2 rounded-lg font-medium transition-all ${
            activeTab === 'upload'
              ? 'bg-purple-500/20 text-purple-400'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          📤 Загрузка PDF
        </button>
      </div>

      <div className="ios-card">
        {activeTab === 'pricelist' && <PricelistManager />}
        {activeTab === 'upload' && <UploadPricelist />}
      </div>
    </div>
  )
}
