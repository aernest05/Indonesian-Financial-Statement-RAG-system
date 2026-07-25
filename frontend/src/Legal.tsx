import type { ReactNode } from 'react'
import './Pricing.css'
import './Legal.css'

const OPERATOR = 'Alexander Ernest'
const CONTACT_EMAIL = 'alexanderernest2010@gmail.com'
const PRODUCT_NAME = 'FinSage'
const PRICE = 'Rp 40.000/bulan'

function LegalShell({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <div className="pricing-page">
      <header className="pricing-topbar">
        <a href="/" className="pricing-brand">
          <div className="brand-icon brand-icon--sm">FS</div>
          <span>{PRODUCT_NAME}</span>
        </a>
        <a href="/pricing" className="pricing-back">← Kembali ke harga</a>
      </header>

      <main className="pricing-main legal-main">
        <div className="pricing-hero">
          <h1>{title}</h1>
          <p className="legal-updated">Terakhir diperbarui: {updated}</p>
        </div>
        <div className="legal-content">{children}</div>
      </main>
    </div>
  )
}

export function TermsOfService() {
  return (
    <LegalShell title="Syarat & Ketentuan" updated="25 Juli 2026">
      <p>
        Syarat & Ketentuan ini mengatur penggunaan Anda atas {PRODUCT_NAME}, layanan tanya-jawab
        berbasis AI untuk laporan keuangan emiten Indonesia, yang dioperasikan oleh {OPERATOR}
        ("kami"). Dengan menggunakan {PRODUCT_NAME}, Anda menyetujui syarat berikut.
      </p>

      <h2>1. Layanan</h2>
      <p>
        {PRODUCT_NAME} menyediakan akses ke chatbot yang menjawab pertanyaan seputar laporan
        keuangan resmi emiten yang terdaftar di Bursa Efek Indonesia (BEI), lengkap dengan kutipan
        sumber dokumen PDF. Tersedia paket Free dan Pro ({PRICE}).
      </p>

      <h2>2. Akun</h2>
      <p>
        Anda masuk menggunakan akun Google melalui penyedia autentikasi pihak ketiga (Supabase).
        Anda bertanggung jawab menjaga keamanan akun Google Anda.
      </p>

      <h2>3. Pembayaran & Langganan Pro</h2>
      <p>
        Paket Pro dibayar di muka melalui mitra pembayaran Midtrans dan memberikan akses tanpa
        batas harian selama 30 hari sejak pembayaran berhasil. Langganan Pro <strong>tidak
        diperpanjang otomatis</strong> — setelah 30 hari, akun kembali ke paket Free hingga Anda
        melakukan pembayaran ulang. Lihat Kebijakan Pengembalian Dana untuk ketentuan refund.
      </p>

      <h2>4. Batasan Layanan</h2>
      <p>
        Jawaban yang dihasilkan oleh {PRODUCT_NAME} berbasis AI dan disusun dari dokumen laporan
        keuangan publik. Meskipun kami berupaya menjaga akurasi, jawaban dapat mengandung kesalahan
        dan <strong>bukan merupakan nasihat investasi, keuangan, atau hukum</strong>. Keputusan
        investasi sepenuhnya menjadi tanggung jawab Anda.
      </p>

      <h2>5. Penggunaan yang Wajar</h2>
      <p>
        Anda setuju untuk tidak menyalahgunakan layanan, termasuk namun tidak terbatas pada upaya
        scraping otomatis di luar antarmuka yang disediakan, atau upaya membebani sistem secara
        berlebihan.
      </p>

      <h2>6. Perubahan Layanan</h2>
      <p>
        Kami dapat mengubah, menambah, atau menghentikan fitur layanan sewaktu-waktu. Perubahan
        material pada syarat ini akan diperbarui pada halaman ini.
      </p>

      <h2>7. Kontak</h2>
      <p>
        Pertanyaan mengenai Syarat & Ketentuan ini dapat dikirim ke{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalShell>
  )
}

export function PrivacyPolicy() {
  return (
    <LegalShell title="Kebijakan Privasi" updated="25 Juli 2026">
      <p>
        Kebijakan Privasi ini menjelaskan data apa yang kami kumpulkan saat Anda menggunakan{' '}
        {PRODUCT_NAME} dan bagaimana data tersebut digunakan.
      </p>

      <h2>1. Data yang Kami Kumpulkan</h2>
      <ul>
        <li>Nama dan alamat email dari akun Google Anda (melalui Supabase Auth) saat Anda masuk.</li>
        <li>Riwayat percakapan dan pertanyaan yang Anda kirimkan, disimpan agar Anda dapat melanjutkan percakapan.</li>
        <li>Status langganan dan data transaksi pembayaran (diproses oleh Midtrans — kami tidak menyimpan detail kartu atau rekening Anda).</li>
        <li>Data teknis dasar (seperti alamat IP) untuk mencegah penyalahgunaan dan membatasi kuota harian.</li>
      </ul>

      <h2>2. Penggunaan Data</h2>
      <p>
        Data digunakan untuk mengoperasikan layanan: menjawab pertanyaan Anda, menyimpan riwayat
        percakapan, mengelola status langganan, dan menegakkan batas kuota harian pada paket Free.
        Kami tidak menjual data pribadi Anda kepada pihak ketiga.
      </p>

      <h2>3. Pihak Ketiga</h2>
      <p>
        Kami menggunakan penyedia layanan pihak ketiga untuk mengoperasikan {PRODUCT_NAME}:
        Supabase (autentikasi & penyimpanan data) dan Midtrans (pemrosesan pembayaran). Masing-masing
        tunduk pada kebijakan privasi mereka sendiri.
      </p>

      <h2>4. Penyimpanan & Keamanan</h2>
      <p>
        Data disimpan pada infrastruktur Supabase dengan akses dibatasi hanya untuk operasional
        layanan. Anda dapat meminta penghapusan akun dan data terkait dengan menghubungi kami.
      </p>

      <h2>5. Hak Anda</h2>
      <p>
        Anda dapat meminta akses, koreksi, atau penghapusan data pribadi Anda kapan saja dengan
        menghubungi <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>

      <h2>6. Kontak</h2>
      <p>
        Pertanyaan mengenai privasi dapat dikirim ke{' '}
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>
    </LegalShell>
  )
}

export function RefundPolicy() {
  return (
    <LegalShell title="Kebijakan Pengembalian Dana" updated="25 Juli 2026">
      <p>
        Paket Pro {PRODUCT_NAME} ({PRICE}) adalah pembayaran satu kali yang memberikan akses 30
        hari dan <strong>tidak diperpanjang otomatis</strong>. Kebijakan berikut berlaku untuk
        setiap pembayaran yang diproses melalui Midtrans.
      </p>

      <h2>1. Kapan Refund Diberikan</h2>
      <ul>
        <li>Pembayaran berhasil diproses namun akun Anda tidak ter-upgrade ke Pro dalam waktu 1×24 jam.</li>
        <li>Anda dikenakan biaya lebih dari satu kali (double charge) untuk transaksi yang sama.</li>
        <li>Kegagalan teknis di pihak kami yang menyebabkan layanan Pro tidak dapat diakses sama sekali selama periode aktif.</li>
      </ul>

      <h2>2. Kapan Refund Tidak Diberikan</h2>
      <p>
        Karena akses Pro diberikan segera setelah pembayaran berhasil, kami tidak memberikan refund
        untuk alasan berubah pikiran setelah akses aktif, atau untuk sisa hari yang tidak
        digunakan dalam periode 30 hari yang sudah berjalan.
      </p>

      <h2>3. Cara Mengajukan Refund</h2>
      <p>
        Kirim email ke <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> dengan menyertakan
        email akun Anda dan bukti transaksi (order ID Midtrans / bukti pembayaran) maksimal 7 hari
        setelah transaksi. Refund yang disetujui akan diproses ke metode pembayaran asal dalam
        7–14 hari kerja.
      </p>
    </LegalShell>
  )
}
