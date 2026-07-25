import { useState } from 'react'
import { supabase } from './supabase'
import './Landing.css'

const FEATURES = [
  {
    icon: '🔍',
    title: 'Retrieval-Augmented Generation',
    desc: 'Jawaban didasarkan langsung pada dokumen laporan keuangan resmi, bukan tebakan model.',
  },
  {
    icon: '⚡',
    title: 'Jawaban Streaming Real-time',
    desc: 'Lihat jawaban muncul secara langsung saat AI menyusunnya, tanpa menunggu lama.',
  },
  {
    icon: '📄',
    title: 'Sumber Terverifikasi',
    desc: 'Setiap jawaban dilengkapi kutipan dan tautan langsung ke PDF laporan aslinya.',
  },
  {
    icon: '📊',
    title: 'Analisis Rasio Keuangan',
    desc: 'ROE, ROA, CAR, NPL, LDR, dan metrik keuangan lain dihitung dan dijelaskan otomatis.',
  },
  {
    icon: '🏦',
    title: 'Cakupan Multi-Emiten',
    desc: 'Data dari berbagai emiten perbankan dan sektor lain yang terdaftar di BEI.',
  },
  {
    icon: '💬',
    title: 'Riwayat Percakapan Tersimpan',
    desc: 'Masuk dengan Google untuk menyimpan dan melanjutkan percakapan kapan saja.',
  },
]

const STEPS = [
  { n: '1', title: 'Tanya', desc: 'Ketik pertanyaan seputar laporan keuangan dalam bahasa natural.' },
  { n: '2', title: 'Cari & Analisis', desc: 'FinSage mencari bagian paling relevan dari dokumen resmi emiten.' },
  { n: '3', title: 'Jawaban + Sumber', desc: 'Dapatkan jawaban akurat lengkap dengan kutipan dokumen aslinya.' },
]

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

export default function Landing() {
  const [signingIn, setSigningIn] = useState(false)

  const handleSignIn = () => {
    setSigningIn(true)
    supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/app` },
    })
  }

  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-brand">
          <div className="brand-icon brand-icon--sm">FS</div>
          <span>FinSage</span>
        </div>
        <nav className="landing-nav-links">
          <a href="#features">Fitur</a>
          <a href="#pricing">Harga</a>
        </nav>
        <div className="landing-nav-cta">
          <button className="landing-btn landing-btn--ghost" onClick={handleSignIn} disabled={signingIn}>
            Masuk
          </button>
          <a href="/app" className="landing-btn landing-btn--primary">Coba Gratis</a>
        </div>
      </header>

      <main>
        {/* ── Hero ── */}
        <section className="landing-hero">
          <span className="landing-eyebrow">RAG untuk Laporan Keuangan Indonesia</span>
          <h1>Tanya apa saja tentang laporan keuangan emiten Indonesia.</h1>
          <p>
            FinSage menganalisis laporan keuangan resmi BBRI, BBCA, BMRI, dan emiten lainnya —
            lengkap dengan sumber dokumen PDF untuk setiap jawaban.
          </p>
          <div className="landing-hero-cta">
            <a href="/app" className="landing-btn landing-btn--primary landing-btn--lg">
              Mulai chat gratis →
            </a>
            <a href="#pricing" className="landing-btn landing-btn--ghost landing-btn--lg">
              Lihat harga
            </a>
          </div>

          <div className="landing-demo">
            <div className="landing-demo-msg landing-demo-msg--user">
              Berapa ROE BBCA untuk tahun 2025?
            </div>
            <div className="landing-demo-msg landing-demo-msg--assistant">
              ROE BBCA untuk tahun 2025 tercatat sebesar 22,4%, mencerminkan efisiensi
              tinggi dalam menghasilkan laba dari ekuitas pemegang saham…
              <div className="landing-demo-source">📄 1 sumber — Laporan Keuangan BBCA FY2025.pdf</div>
            </div>
          </div>
        </section>

        {/* ── Features ── */}
        <section id="features" className="landing-section">
          <h2>Kenapa FinSage?</h2>
          <p className="landing-section-sub">
            Dibangun khusus untuk investor dan analis yang butuh jawaban cepat dan akurat dari data resmi.
          </p>
          <div className="landing-features-grid">
            {FEATURES.map(f => (
              <div key={f.title} className="landing-feature-card">
                <span className="landing-feature-icon">{f.icon}</span>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="landing-section landing-section--alt">
          <h2>Cara kerjanya</h2>
          <div className="landing-steps">
            {STEPS.map(s => (
              <div key={s.n} className="landing-step">
                <div className="landing-step-num">{s.n}</div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Pricing ── */}
        <section id="pricing" className="landing-section">
          <h2>Harga sederhana, tanpa kejutan</h2>
          <p className="landing-section-sub">
            Mulai gratis, upgrade kapan saja untuk akses tanpa batas.
          </p>

          <div className="landing-pricing-grid">
            <div className="landing-pricing-card">
              <div className="landing-pricing-card-header">
                <h3>Free</h3>
                <p>Untuk mencoba FinSage</p>
              </div>
              <div className="landing-pricing-price">
                <span className="landing-pricing-amount">Rp 0</span>
                <span className="landing-pricing-period">/bulan</span>
              </div>
              <ul className="landing-pricing-features">
                {FEATURES_FREE.map(f => (
                  <li key={f}><span className="landing-pricing-check">✓</span>{f}</li>
                ))}
              </ul>
              <a href="/app" className="landing-btn landing-btn--ghost">Mulai gratis</a>
            </div>

            <div className="landing-pricing-card landing-pricing-card--featured">
              <div className="landing-pricing-badge">Paling populer</div>
              <div className="landing-pricing-card-header">
                <h3>Pro</h3>
                <p>Untuk investor & analis aktif</p>
              </div>
              <div className="landing-pricing-price">
                <span className="landing-pricing-amount">Rp 40.000</span>
                <span className="landing-pricing-period">/bulan</span>
              </div>
              <ul className="landing-pricing-features">
                {FEATURES_PRO.map(f => (
                  <li key={f}><span className="landing-pricing-check">✓</span>{f}</li>
                ))}
              </ul>
              <a href="/pricing" className="landing-btn landing-btn--primary">✦ Upgrade ke Pro</a>
            </div>
          </div>

          <p className="landing-pricing-detail-link">
            <a href="/pricing">Lihat detail lengkap harga →</a>
          </p>
        </section>

        {/* ── Final CTA ── */}
        <section className="landing-cta-banner">
          <h2>Siap coba FinSage?</h2>
          <p>Mulai analisis laporan keuangan emiten favoritmu hari ini — gratis.</p>
          <a href="/app" className="landing-btn landing-btn--primary landing-btn--lg">
            Mulai chat gratis →
          </a>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-brand">
          <div className="brand-icon brand-icon--sm">FS</div>
          <span>FinSage</span>
        </div>
        <div className="landing-footer-links">
          <a href="#features">Fitur</a>
          <a href="#pricing">Harga</a>
          <a href="/pricing">Detail harga</a>
          <a href="/terms">Syarat & Ketentuan</a>
          <a href="/privacy">Kebijakan Privasi</a>
          <a href="/refund">Kebijakan Refund</a>
        </div>
        <p className="landing-footer-copy">© {new Date().getFullYear()} FinSage. Semua hak dilindungi.</p>
      </footer>
    </div>
  )
}
