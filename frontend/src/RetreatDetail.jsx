import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { ArrowRight, CalendarDays, Clock3, Download, MapPin, MessageCircle, Ticket } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router-dom'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => {
  const token = localStorage.getItem('retunori_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

const parseWallClock = value => {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (!match) return null
  const [, year, month, day, hour, minute] = match
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour) - 3, Number(minute)))
}

const formatWallClock = value => parseWallClock(value)?.toLocaleString('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC'
}) || ''

function Countdown({ target }) {
  const targetTime = parseWallClock(target)?.getTime() || 0
  const [remaining, setRemaining] = useState(Math.max(0, targetTime - Date.now()))
  useEffect(() => { const timer = window.setInterval(() => setRemaining(Math.max(0, targetTime - Date.now())), 1000); return () => window.clearInterval(timer) }, [targetTime])
  const seconds = Math.floor(remaining / 1000); const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600); const minutes = Math.floor((seconds % 3600) / 60)
  return <div className="countdown" aria-label={`${days} days until this retreat`}><span><strong>{days}</strong><small>days</small></span><span><strong>{String(hours).padStart(2, '0')}</strong><small>hours</small></span><span><strong>{String(minutes).padStart(2, '0')}</strong><small>minutes</small></span></div>
}

export default function RetreatDetail() {
  const { slug } = useParams(); const location = useLocation(); const [retreat, setRetreat] = useState(null); const [support, setSupport] = useState(null); const [tickets, setTickets] = useState([]); const [error, setError] = useState(''); const preview = new URLSearchParams(location.search).get('preview') === '1'
  useEffect(() => { Promise.all([api.get(preview ? `/admin/retreats/preview/${slug}` : `/retreats/${slug}`), api.get('/homepage')]).then(([r, h]) => { setRetreat(r.data); setSupport(h.data.content) }).catch(e => setError(e.response?.data?.detail || 'Retreat not found')) }, [slug, preview])
  useEffect(() => {
    if (!localStorage.getItem('retunori_token')) return
    api.get('/me/tickets').then(response => setTickets(response.data)).catch(() => {})
  }, [])
  if (error) return <section className="page section"><h1>Retreat unavailable.</h1><p className="muted">{error}</p><Link className="text-link" to="/retreats">Browse retreats</Link></section>
  if (!retreat) return <div className="loading">Loading retreat…</div>
  const mapUrl = retreat.location_url || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${retreat.venue}, Kenya`)}`
  const deadline = parseWallClock(retreat.sales_closes_at)
  const open = retreat.sales_open && retreat.remaining_capacity > 0 && (!deadline || deadline.getTime() > Date.now())
  const registrationStatus = retreat.remaining_capacity === 0 ? 'SOLD OUT' : open ? 'REGISTRATION OPEN' : 'REGISTRATION CLOSED'
  const bookedTicket = tickets.find(ticket => ticket.retreat_title === retreat.title)
  const downloadTicket = async () => {
    try {
      const response = await api.get(`/me/tickets/${bookedTicket.ticket_number}/pdf`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `${bookedTicket.ticket_number}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('The ticket could not be downloaded. Please try again.')
    }
  }
  return <section className="detail page section"><Link className="text-link" to="/retreats">← All retreats</Link><div className="detail-grid"><div className="retreat-gallery">{retreat.images?.length ? retreat.images.map(image => <img key={image.id} src={image.url} alt={image.alt_text} loading="lazy" decoding="async" onError={event => { event.currentTarget.style.display = 'none' }}/>) : <div className="poster large"><span>RETUNORI<br/><b>{retreat.title}</b></span></div>}</div><div><div className="eyebrow">{bookedTicket ? 'TICKET BOOKED' : registrationStatus}</div><h1>{retreat.title}</h1>{bookedTicket && <p className="booked-event-ticket"><Ticket size={18}/> Your ticket: <strong>{bookedTicket.ticket_number}</strong></p>}<p className="lead">{retreat.description}</p><div className="facts"><span><CalendarDays/> {new Date(retreat.starts_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</span><span><Clock3/> {new Date(retreat.starts_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} – {new Date(retreat.ends_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}</span><span><MapPin/> {retreat.venue}</span><span><Ticket/> {retreat.is_free ? 'FREE' : `KES ${retreat.price_kes.toLocaleString()}`} · {retreat.remaining_capacity} places left</span></div>{retreat.sales_closes_at && <p className="registration-deadline">{open ? 'Registration open until' : 'Registration closed on'} <strong>{formatWallClock(retreat.sales_closes_at)}</strong></p>}<Countdown target={retreat.starts_at}/><div className="detail-actions">{bookedTicket ? <button type="button" className="button primary" onClick={downloadTicket}>Download your ticket <Download size={17}/></button> : open ? <Link to={`/purchase?retreat=${retreat.id}`} className="button primary">Get your ticket <ArrowRight size={17}/></Link> : <button type="button" className="button primary" disabled>Registration closed</button>}<a className="button secondary" href={mapUrl} target="_blank" rel="noreferrer"><MapPin size={16}/> Directions</a></div></div></div></section>
}
