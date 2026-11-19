import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// Шрифты лежат вместе с сайтом, без обращений к Google Fonts.
import '@fontsource/amatic-sc/cyrillic-700.css'
import '@fontsource/amatic-sc/latin-700.css'
import '@fontsource/lora/cyrillic-400.css'
import '@fontsource/lora/latin-400.css'
import '@fontsource/lora/cyrillic-400-italic.css'
import '@fontsource/lora/cyrillic-600.css'
import '@fontsource/lora/latin-600.css'
import ShopApp from './ShopApp.jsx'
import './shop.css'

// Витрина открыта на /shop или в корне домена магазина (OIL_SHOP_HOST).
const basename = window.location.pathname.startsWith('/shop') ? '/shop' : ''

ReactDOM.createRoot(document.getElementById('shop-root')).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <ShopApp />
    </BrowserRouter>
  </React.StrictMode>,
)
