import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Mail } from 'lucide-react'

const api = axios.create({ baseURL: '/api' })

export function AnnouncementsPage() {
  const [items, setItems] = useState([]); const [error, setError] = useState('')
  const [gallery, setGallery] = useState(null)
  useEffect(() => { api.get('/announcements').then(r => setItems(r.data)).catch(() => setError('Announcements are temporarily unavailable.')) }, [])
  const formatDate = value => value ? new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : ''
  const [featured, ...rest] = items
  return <main className="journal-page">
    <section className="journal-hero">
      <div className="journal-hero-copy">
        <div className="eyebrow">THE RETUNORI JOURNAL</div>
        <h1>Stories for living<br/><em>with intention.</em></h1>
        <p className="lead">Thoughts, field notes, community moments, and practical ideas for a more connected life.</p>
      </div>
      <div className="journal-hero-mark" aria-hidden="true"><span>J</span></div>
    </section>
    {error && <section className="journal-shell"><p className="error">{error}</p></section>}
    {featured && <section className="journal-shell journal-featured-wrap">
      <article className="journal-featured">
        <div className={`journal-featured-art${featured.image_urls?.length ? ' has-gallery' : ''}`}>
          {featured.image_urls?.[0] ? <img src={featured.image_urls[0]} alt={`${featured.title} gallery preview`}/> : <span>RETUNORI<br/>JOURNAL</span>}
        </div>
        <div className="journal-featured-copy">
          <div className="journal-meta">COMMUNITY NOTES <span /> {formatDate(featured.published_at)}</div>
          <h2>{featured.title}</h2>
          <p>{featured.body}</p>
          {featured.image_urls?.length ? <button className="journal-read journal-gallery-button" type="button" onClick={() => setGallery(featured)}>View all {featured.image_urls.length} photos <ArrowRight size={17}/></button> : <span className="journal-read">Read the story <ArrowRight size={17}/></span>}
        </div>
      </article>
    </section>}
    <section className="journal-shell">
      <div className="journal-section-head"><div><div className="eyebrow">LATEST STORIES</div><h2>From the community</h2></div><span>{items.length} {items.length === 1 ? 'story' : 'stories'}</span></div>
      {rest.length ? <div className="journal-grid">{rest.map((item, index) => <article className="journal-card" key={item.id}>
        <div className={`journal-card-art art-${index % 3}${item.image_urls?.length ? ' has-gallery' : ''}`}>{item.image_urls?.[0] ? <img src={item.image_urls[0]} alt={`${item.title} gallery preview`}/> : <span>{String(index + 2).padStart(2, '0')}</span>}</div>
        <div className="journal-card-body">
          <div className="journal-meta">RETUNORI NOTES <span /> {formatDate(item.published_at)}</div>
          <h3>{item.title}</h3>
          <p>{item.body}</p>
          {item.image_urls?.length ? <button className="journal-read journal-gallery-button" type="button" onClick={() => setGallery(item)}>View all {item.image_urls.length} photos <ArrowRight size={16}/></button> : <span className="journal-read">Read story <ArrowRight size={16}/></span>}
        </div>
      </article>)}</div> : !featured && !error && <div className="journal-empty"><h2>The next chapter is on its way.</h2><p className="muted">New stories and community updates will be published here soon.</p></div>}
    </section>
    {gallery && <div className="journal-gallery-modal" role="dialog" aria-modal="true" aria-label={`${gallery.title} photo gallery`} onClick={() => setGallery(null)}>
      <div className="journal-gallery-panel" onClick={event => event.stopPropagation()}>
        <div className="journal-gallery-heading"><div><div className="eyebrow">{gallery.retreat_title || 'RETUNORI EVENT'}</div><h2>{gallery.title}</h2></div><button type="button" aria-label="Close gallery" onClick={() => setGallery(null)}>×</button></div>
        <div className="journal-gallery-grid">{gallery.image_urls.map((url, index) =>
          <article className="journal-gallery-photo" key={url}>
            <button type="button" onClick={() => window.open(url, '_blank', 'noopener')}><img src={url} alt={`${gallery.title} photo ${index + 1}`}/></button>
            <a href={url} download={`retunori-${gallery.id}-${index + 1}.webp`}>Download WebP</a>
          </article>
        )}</div>
        <p className="muted">Available until {new Date(gallery.expires_at).toLocaleString()}.</p>
      </div>
    </div>}
  </main>
}

export function ContactPage() {
  const [form, setForm] = useState({ name:'', email:'', message:'' }); const [support, setSupport] = useState({ support_email: 'hello@retunori.com', support_phone: '' }); const [status, setStatus] = useState('')
  useEffect(() => { api.get('/homepage').then(response => setSupport(response.data.content || support)).catch(() => {}) }, [])
  const submit = async event => { event.preventDefault(); setStatus(''); try { await api.post('/contact', form); setStatus('Thanks. Your message has been received.'); setForm({name:'',email:'',message:''}) } catch { setStatus('We could not send that message. Please try again.') } }
  const whatsapp = support.support_phone ? `https://wa.me/${support.support_phone.replace(/\D/g, '').replace(/^0/, '254')}` : ''
  return <section className="page section"><Link className="back-link" to="/"><ArrowLeft size={16}/> Back to home</Link><div className="eyebrow"><Mail size={14}/> SUPPORT</div><h1>Get in touch.</h1><p className="lead">Have a question about a retreat? Send a message to the RETUNORI team.</p><div className="support-links"><a className="text-link" href={`mailto:${support.support_email}`}>{support.support_email}</a>{support.support_phone && <a className="text-link" href={`tel:${support.support_phone}`}>{support.support_phone}</a>}{whatsapp && <a className="text-link" href={whatsapp} target="_blank" rel="noreferrer">WhatsApp support</a>}</div><form className="contact-form" onSubmit={submit}><input required placeholder="Your name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input required type="email" placeholder="Email address" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><textarea required placeholder="How can we help?" value={form.message} onChange={e=>setForm({...form,message:e.target.value})}/><button className="button primary" type="submit">Send message <ArrowRight size={16}/></button>{status && <p className="muted">{status}</p>}</form></section>
}

export function LegalPage({ slug }) {
  const [page, setPage] = useState(null); useEffect(() => { api.get(`/legal/${slug}`).then(r=>setPage(r.data)).catch(()=>setPage(false)) }, [slug])
  if (page === null) return <div className="loading">Loading…</div>
  if (page === false) return <section className="page section"><h1>Page unavailable.</h1><p className="lead">This legal page has not been published yet.</p></section>
  return <section className="page section legal"><Link className="back-link" to="/"><ArrowLeft size={16}/> Back to home</Link><div className="eyebrow">RETUNORI POLICY</div><h1>{page.title}</h1><div className="legal-copy">{page.body}</div></section>
}
