import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Pricing from './Pricing.tsx'
import Landing from './Landing.tsx'
import { TermsOfService, PrivacyPolicy, RefundPolicy } from './Legal.tsx'

const path = window.location.pathname
const page =
  path === '/pricing' ? <Pricing /> :
  path === '/terms' ? <TermsOfService /> :
  path === '/privacy' ? <PrivacyPolicy /> :
  path === '/refund' ? <RefundPolicy /> :
  path === '/' ? <Landing /> :
  <App />

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {page}
  </StrictMode>,
)
