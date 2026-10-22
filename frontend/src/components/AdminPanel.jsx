import { useState } from 'react'
import AdminAnalytics from './AdminAnalytics'
import ImportOrdersPanel from './ImportOrdersPanel'
import PageHeader from './PageHeader'
import PricelistManager from './PricelistManager'
import SettingsPanel from './SettingsPanel'
import UploadPricelist from './UploadPricelist'
import UsersPanel from './UsersPanel'

const tabs = [
  { id: 'analytics', label: 'Аналитика, партии и расходы' },
  { id: 'pricelist', label: 'Прайс-лист' },
  { id: 'upload', label: 'Загрузка прайса' },
  { id: 'import', label: 'Импорт заказов' },
  { id: 'settings', label: 'Настройки' },
  { id: 'users', label: 'Пользователи' },
]

export default function AdminPanel({ user }) {
  const [activeTab, setActiveTab] = useState('analytics')

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Управление"
        title="Управление"
        description="Аналитика и учёт производства, прайс-лист, настройки прессов и доступы сотрудников."
      />

      <div className="filter-row filter-row--start">
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
        {activeTab === 'import' ? <ImportOrdersPanel isAdmin={user?.role === 'admin' && !user?.is_demo} /> : null}
        {activeTab === 'settings' ? <SettingsPanel isAdmin={user?.role === 'admin'} /> : null}
        {activeTab === 'users' ? <UsersPanel user={user} /> : null}
      </section>
    </div>
  )
}
