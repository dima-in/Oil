import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useDataRefresh } from '../lib/events'
import { money } from '../lib/format'
import { useAssistant } from './assistant/AssistantContext'

const SETTINGS_FIELDS = [
  ['bottle_cost', 'Бутылка, ₽'],
  ['seed_delivery_per_kg', 'Доставка семян, ₽ за кг'],
  ['tax_percent', 'Налог, %'],
]

function num(value, digits = 0) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits })
}

const BASIS = {
  sales: 'по продажам за год',
  price_list: 'по прайсу, продаж не было',
}

// «Получка за закладку» считается сама: выход × маржа с мл при текущих ценах.
function BatchPay({ oil }) {
  const pay = oil?.batch_pay
  if (!pay) return <span className="muted">нужна цена семян</span>
  return (
    <>
      <strong>{money(pay.value)}</strong>
      <div className="cell-note muted">
        {BASIS[pay.basis]}
        {pay.max - pay.min >= 1 ? ` · от ${money(pay.min)} до ${money(pay.max)}` : ''}
      </div>
      {oil.table_pay ? <div className="cell-note muted">в старой таблице {money(oil.table_pay)}</div> : null}
    </>
  )
}

function NormRow({ profile, oil, isAdmin, onSaved }) {
  const kg = Number(profile.batch_seed_weight_kg || 0)
  const [form, setForm] = useState({
    kg: profile.batch_seed_weight_kg ?? '',
    yieldMl: kg ? Math.round(kg * Number(profile.yield_percent || 0) * 10) : '',
    seedPrice: profile.seed_price_per_kg ?? '',
  })
  const [saving, setSaving] = useState(false)
  const set = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  const save = async () => {
    const kgValue = Number(String(form.kg).replace(',', '.'))
    const yieldMl = Number(String(form.yieldMl).replace(',', '.'))
    if (!kgValue || !yieldMl) {
      alert('Нужны кг в закладке и выход масла')
      return
    }
    setSaving(true)
    try {
      await api.saveProductionProfile({
        oil_name: profile.oil_name,
        batch_seed_weight_kg: kgValue,
        yield_percent: yieldMl / (kgValue * 10),
        daily_batch_limit: profile.daily_batch_limit,
        note: profile.note,
        seed_price_per_kg: form.seedPrice === '' ? null : Number(String(form.seedPrice).replace(',', '.')),
      })
      onSaved()
    } catch (error) {
      alert(error.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr>
      <td>{profile.oil_name}</td>
      {[
        ['kg', '0.1'],
        ['yieldMl', '10'],
        ['seedPrice', '1'],
      ].map(([field, step]) => (
        <td key={field} className="num">
          <input className="ios-input table-input" type="number" step={step} min="0" value={form[field]}
            onChange={set(field)} disabled={!isAdmin} />
        </td>
      ))}
      <td className="num">{oil?.batch_pay ? money(oil.batch_pay.cost) : '—'}</td>
      <td className="num">
        <BatchPay oil={oil} />
      </td>
      <td>
        {isAdmin ? (
          <button type="button" className="link-button" onClick={save} disabled={saving}>
            {saving ? '…' : 'Сохранить'}
          </button>
        ) : null}
      </td>
    </tr>
  )
}

// Юнит-экономика: нормы себестоимости по маслам и маржа каждой бутылки прайса.
export default function EconomicsPanel({ isAdmin }) {
  const [economics, setEconomics] = useState(null)
  const [profiles, setProfiles] = useState([])
  const [settingsForm, setSettingsForm] = useState(null)
  const [notice, setNotice] = useState(null)
  const assistant = useAssistant()
  const oilsByName = Object.fromEntries((economics?.oils || []).map((oil) => [oil.oil_name, oil]))

  const load = useCallback(async () => {
    try {
      const [data, rows] = await Promise.all([api.crm.economics(), api.getProductionProfiles()])
      setEconomics(data)
      setProfiles(rows)
      setSettingsForm(data.settings)
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при открытии вкладки
    load()
  }, [load])
  useDataRefresh(load)

  const saveSettings = async (event) => {
    event.preventDefault()
    try {
      await api.crm.updateSettings(settingsForm)
      setNotice({ type: 'success', text: 'Сохранено — маржа пересчитана.' })
      load()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    }
  }

  if (!economics || !settingsForm) {
    return notice ? <div className={`notice notice--${notice.type}`}>{notice.text}</div> : <div className="state-panel">Считаю…</div>
  }

  return (
    <div className="page-stack page-stack--compact">
      <div className="section-head">
        <div>
          <h3 className="section-head__title">Экономика бутылки</h3>
          <p className="section-head__text">
            Маржа = цена − семена − доставка семян − бутылка − налог. Это то, что остаётся вам до аренды,
            каршеринга, комиссий Ozon/Avito и прочих общих расходов. Затраты считаются сами — из расхода семян на
            закладку и их цены, а «получка за закладку» = выручка с закладки − затраты при текущих ценах, с учётом
            того, какие бутылки покупали за год. Нормы можно загрузить из старой таблицы («Импорт заказов» читает
            лист «Прайс») или поправить здесь.
          </p>
        </div>
        <button
          type="button"
          className="ios-button secondary"
          onClick={() => assistant.ask('Проанализируй экономику масел: где маржа низкая, что поднять в цене, где скидка за объём съедает прибыль.')}
        >
          Разбор от ИИ
        </button>
      </div>

      {notice ? <div className={`notice notice--${notice.type}`}>{notice.text}</div> : null}
      {economics.warnings.length ? (
        <div className="notice notice--warning">
          {economics.warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}

      <form className="settings-grid" onSubmit={saveSettings}>
        {SETTINGS_FIELDS.map(([field, label]) => (
          <label key={field} className="field">
            <span className="field__label">{label}</span>
            <input className="ios-input" type="number" step="0.5" min="0" value={settingsForm[field]}
              onChange={(event) => setSettingsForm((prev) => ({ ...prev, [field]: event.target.value }))}
              disabled={!isAdmin} />
          </label>
        ))}
        {isAdmin ? (
          <div className="field">
            <span className="field__label">&nbsp;</span>
            <button type="submit" className="ios-button primary">Сохранить</button>
          </div>
        ) : null}
      </form>

      <h4 className="crm-block__title">Нормы по маслам</h4>
      <div className="table-wrap">
        <table className="price-table price-table--compact crm-table">
          <thead>
            <tr>
              <th>Масло</th>
              <th className="num">Кг в закладке</th>
              <th className="num">Выход, мл</th>
              <th className="num">Семена, ₽/кг</th>
              <th className="num" title="Семена по расходу и цене, доставка семян, бутылки, налог">Затраты на закладку</th>
              <th className="num">Получка за закладку</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {profiles.map((profile) => (
              <NormRow key={`${profile.id}-${profile.seed_price_per_kg}`} profile={profile}
                oil={oilsByName[profile.oil_name]} isAdmin={isAdmin} onSaved={load} />
            ))}
            {!profiles.length ? (
              <tr>
                <td colSpan={7} className="price-table__empty">Норм пока нет — загрузите их импортом из Excel.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <h4 className="crm-block__title">Маржа каждой бутылки</h4>
      <div className="table-wrap">
        <table className="price-table price-table--compact crm-table">
          <thead>
            <tr>
              <th>Масло</th>
              <th className="num">Объём</th>
              <th className="num">Цена</th>
              <th className="num">Маржа</th>
              <th className="num">Маржа %</th>
              <th className="num">Семена</th>
              <th className="num">Доставка</th>
              <th className="num">Бутылка</th>
              <th className="num">Налог</th>
              <th className="num" title="Получка, если разлить всю закладку в бутылки этого объёма">За закладку</th>
            </tr>
          </thead>
          <tbody>
            {economics.items.map((item) => (
              <tr key={`${item.oil_name}-${item.volume}`} className={item.low ? 'row--warning' : ''}>
                <td>{item.oil_name}</td>
                <td className="num">{item.volume} мл</td>
                <td className="num">{money(item.price)}</td>
                <td className="num"><strong>{item.margin === null ? '—' : money(item.margin)}</strong></td>
                <td className="num">{item.margin_percent === null ? '—' : `${num(item.margin_percent)}%`}</td>
                <td className="num">{item.margin === null ? <span className="muted">нет цены</span> : num(item.seeds)}</td>
                <td className="num">{num(item.delivery)}</td>
                <td className="num">{num(item.bottle)}</td>
                <td className="num">{num(item.tax)}</td>
                <td className="num muted">{item.batch_pay === null ? '—' : money(item.batch_pay)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
