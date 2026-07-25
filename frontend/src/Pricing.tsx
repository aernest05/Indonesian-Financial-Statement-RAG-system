import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import './Pricing.css'
import './Legal.css'

const API_BASE = import.meta.env.VITE_API_BASE

const FEATURES_FREE = [
  'Batas tanya harian terbatas',
  'Akses ke seluruh laporan keuangan yang tersedia',
  'Sumber dokumen (PDF) untuk setiap jawaban',
]

const FEATURES_PRO = [
  'Tanya tanpa batas harian',
  'Akses ke seluruh laporan keuangan yang tersedia',
  'Sumber dokumen (PDF) untuk setiap jawaban',
  'Riwayat percakapan tersimpan',
  'Dukungan prioritas',
]

export default function Pricing() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => listener.subscription.unsubscribe()
  }, [])

  const handleUpgrade = async () => {
    if (!session) {
      supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${window.location.origin}${window.location.pathname}` },
      })
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/create-checkout-session`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      const data = await res.json()
      if (!res.ok || !data.url) {
        throw new Error(data.detail || `Error ${res.status}`)
      }
      window.location.href = data.url
    } catch (err) {
      alert(`Gagal membuka halaman pembayaran: ${(err as Error).message}`)
      setLoading(false)
    }
  }

  return (
    <div className="pricing-page">
      <header className="pricing-topbar">
        <a href="/" className="pricing-brand">
          <div className="brand-icon brand-icon--sm">FS</div>
          <span>FinSage</span>
        </a>
        <a href="/app" className="pricing-back">← Kembali ke chat</a>
      </header>

      <main className="pricing-main">
        <div className="pricing-hero">
          <h1>Harga sederhana, tanpa kejutan</h1>
          <p>Mulai gratis, upgrade kapan saja untuk akses tanpa batas ke analisis laporan keuangan emiten Indonesia.</p>
        </div>

        <div className="pricing-grid">
          <div className="pricing-card">
            <div className="pricing-card-header">
              <h2>Free</h2>
              <p className="pricing-card-tagline">Untuk mencoba FinSage</p>
            </div>
            <div className="pricing-price">
              <span className="pricing-amount">Rp 0</span>
              <span className="pricing-period">/bulan</span>
            </div>
            <ul className="pricing-features">
              {FEATURES_FREE.map(f => (
                <li key={f}>
                  <span className="pricing-check">✓</span>{f}
                </li>
              ))}
            </ul>
            <a href="/app" className="pricing-cta pricing-cta--secondary">
              Mulai gratis
            </a>
          </div>

          <div className="pricing-card pricing-card--featured">
            <div className="pricing-badge">Paling populer</div>
            <div className="pricing-card-header">
              <h2>Pro</h2>
              <p className="pricing-card-tagline">Untuk investor & analis aktif</p>
            </div>
            <div className="pricing-price">
              <span className="pricing-amount">Rp 40.000</span>
              <span className="pricing-period">/bulan</span>
            </div>
            <ul className="pricing-features">
              {FEATURES_PRO.map(f => (
                <li key={f}>
                  <span className="pricing-check">✓</span>{f}
                </li>
              ))}
            </ul>
            <button className="pricing-cta pricing-cta--primary" onClick={handleUpgrade} disabled={loading}>
              {loading ? 'Memproses…' : session ? '✦ Upgrade ke Pro' : 'Masuk untuk upgrade'}
            </button>
          </div>
        </div>

        <p className="pricing-note">
          Pembayaran diproses secara aman melalui Midtrans. Langganan Pro berlaku 30 hari dan
          tidak diperpanjang otomatis — perpanjang kapan saja Anda mau.
        </p>
        <div className="legal-footer-links">
          <a href="/terms">Syarat & Ketentuan</a>
          <a href="/privacy">Kebijakan Privasi</a>
          <a href="/refund">Kebijakan Refund</a>
        </div>
      </main>
    </div>
  )
}
