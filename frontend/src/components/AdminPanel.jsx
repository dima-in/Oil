import { useState } from 'react'
import AdminAnalytics from './AdminAnalytics'
import PageHeader from './PageHeader'
import PricelistManager from './PricelistManager'
import UploadPricelist from './UploadPricelist'

const tabs = [
  { id: 'pricelist', label: 'Прайс-лист' },
  { id: 'analytics', label: 'Аналитика' },
  { id: 'upload', label: 'Загрузка файла' },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('pricelist')

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Управление"
        title="Админ-панель"
        description="Редактирование прайс-листа и загрузка новых данных."
      />

      <div className="filter-row">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={activeTab === tab.id ? 'filter-chip filter-chip--active' : 'filter-chip'}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <section className="section-card">
        {activeTab === 'pricelist' ? <PricelistManager /> : null}
        {activeTab === 'analytics' ? <AdminAnalytics /> : null}
        {activeTab === 'upload' ? <UploadPricelist /> : null}
      </section>
    </div>
  )
}
