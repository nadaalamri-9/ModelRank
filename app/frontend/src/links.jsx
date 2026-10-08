import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import LinksPage from './pages/LinksPage.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LinksPage />
  </StrictMode>,
)
