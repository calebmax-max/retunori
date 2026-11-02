import React, { useEffect, useRef, useState } from 'react'
import { BarChart3, CheckCircle2, Download, ScanLine, Ticket, TriangleAlert } from 'lucide-react'
import axios from 'axios'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
function Shell({ kicker, title, children }) { return <section className="page section portal"><div className="eyebrow">{kicker}</div><h1>{title}</h1>{children}</section> }

export function AttendeePortal() {
  const [tickets, setTickets] = useState([]); const [error, setError] = useState('')
  useEffect(() => { api.get('/me/tickets').then(r => setTickets(r.data)).catch(e => setError(e.response?.data?.detail || 'Could not load tickets')) }, [])
  return <Shell kicker="YOUR RETUNORI" title="Your retreat space."><div className="portal-grid"><div className="dash-card"><Ticket/><h3>My tickets</h3>{error && <p className="error">{error}</p>}{tickets.length === 0 ? <p className="muted">Verified tickets will appear here after payment confirmation.</p> : tickets.map(ticket => <div className="ticket-row" key={ticket.ticket_number}><div><strong>{ticket.retreat_title}</strong><span>{ticket.ticket_number} · {ticket.course}</span></div><a className="icon-link" href={`/api/me/tickets/${ticket.ticket_number}/pdf`}><Download size={15}/> PDF</a></div>)}</div><div className="dash-card"><CheckCircle2/><h3>Payment history</h3><p className="muted">Payment status is controlled by the RETUNORI backend and Daraja callbacks.</p><span className="empty">Payment records will appear here after you make a purchase.</span></div></div></Shell>
}

export function AdminPortal() {
  const [overview, setOverview] = useState(null); const [reports, setReports] = useState(null); const [notifications, setNotifications] = useState([]); const [error, setError] = useState('')
  useEffect(() => { Promise.all([api.get('/admin/overview'), api.get('/admin/reports'), api.get('/admin/notifications')]).then(([a,b,c]) => { setOverview(a.data); setReports(b.data); setNotifications(c.data) }).catch(e => setError(e.response?.data?.detail || 'Admin access could not be verified')) }, [])
  return <Shell kicker="ADMINISTRATION" title="Operations at a glance.">{error && <div className="error">{error}</div>}<div className="metric-grid">{[['Retreats',overview?.retreats ?? '—'],['Registrations',overview?.registrations ?? '—'],['Paid attendees',overview?.paid_attendees ?? '—'],['Revenue',overview ? `KES ${(overview.revenue_kes || 0).toLocaleString()}` : '—']].map(([label,value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="portal-grid"><div className="dash-card"><BarChart3/><h3>Capacity report</h3>{reports?.retreats?.map(row => <div className="report-row" key={row.id}><span>{row.title}</span><strong>{row.tickets_sold}/{row.capacity}</strong></div>)}<div className="export-links"><a className="icon-link" href="/api/admin/reports/export.xlsx"><Download size={15}/> Excel</a><a className="icon-link" href="/api/admin/reports/export.pdf"><Download size={15}/> PDF</a></div></div><div className="dash-card"><TriangleAlert/><h3>Notifications</h3>{notifications.length ? notifications.slice(0,6).map(n => <div className="report-row" key={n.id}><span>{n.title}</span><small>{new Date(n.created_at).toLocaleDateString()}</small></div>) : <p className="muted">No notifications yet.</p>}</div></div></Shell>
}

function CameraScanner({ onScan }) {
  const videoRef = useRef(null); const streamRef = useRef(null); const [active, setActive] = useState(false); const [message, setMessage] = useState('')
  useEffect(() => () => streamRef.current?.getTracks().forEach(track => track.stop()), [])
  const stop = () => { streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; setActive(false) }
  const start = async () => {
    if (!('BarcodeDetector' in window)) { setMessage('Camera QR scanning is not supported in this browser. Use manual entry.'); return }
    try {
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] }); const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }); streamRef.current = stream; videoRef.current.srcObject = stream; await videoRef.current.play(); setActive(true); setMessage('Point the camera at a RETUNORI ticket QR code.')
      const scan = async () => { if (!streamRef.current) return; try { const codes = await detector.detect(videoRef.current); if (codes[0]?.rawValue) { onScan(codes[0].rawValue); setMessage('QR token captured. Review the value and check in.'); stop(); return } } catch {} window.requestAnimationFrame(scan) }; scan()
    } catch { setMessage('Camera permission was unavailable. Use manual entry.') }
  }
  return <div className="camera-box"><div className="camera-actions"><button type="button" className="button secondary" onClick={active ? stop : start}>{active ? 'Stop camera' : 'Use camera'}</button></div>{active && <video ref={videoRef} muted playsInline className="camera-video"/>}{message && <small className="muted">{message}</small>}</div>
}

export function StaffPortal() {
  const [retreatId, setRetreatId] = useState(''); const [assignments, setAssignments] = useState([]); const [value, setValue] = useState(''); const [method, setMethod] = useState('manual'); const [result, setResult] = useState(null); const [error, setError] = useState('')
  useEffect(() => { api.get('/staff/assignments').then(response => setAssignments(response.data)).catch(() => setError('Assigned retreats could not be loaded')) }, [])
  const submit = async event => { event.preventDefault(); setError(''); setResult(null); try { const response = await api.post('/staff/check-in', { retreat_id: Number(retreatId), value, method }); setResult(response.data) } catch (e) { setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.response?.data?.detail?.status || 'Ticket could not be checked in') } }
  return <Shell kicker="STAFF CHECK-IN" title="Welcome people in."><div className="scanner-card dash-card"><ScanLine/><h3>Verify a ticket</h3><p className="muted">Verify online using the camera, ticket number, QR token, or attendee name. Attendance is never approved offline.</p><form onSubmit={submit} className="checkin-form"><select required value={retreatId} onChange={e=>setRetreatId(e.target.value)}><option value="">Select an assigned retreat</option>{assignments.map(item => <option key={item.id} value={item.id}>{item.title} · {new Date(item.starts_at).toLocaleDateString()}</option>)}</select><select value={method} onChange={e=>setMethod(e.target.value)}><option value="manual">Ticket number / QR token</option><option value="name">Attendee name search</option></select><input placeholder={method === 'name' ? 'Attendee name' : 'Ticket number or QR token'} required value={value} onChange={e=>setValue(e.target.value)}/>{method === 'manual' && <CameraScanner onScan={setValue}/>}<button className="button primary" type="submit">Check in <CheckCircle2 size={16}/></button></form>{error && <div className="error checkin-result">{error}</div>}{result?.status === 'multiple_matches' && <div className="checkin-result"><strong>Multiple matches found</strong>{result.matches.map(item => <button type="button" className="secondary" key={item.ticket_number} onClick={() => {setValue(item.ticket_number); setMethod('manual')}}>{item.attendee_name} · {item.ticket_number}</button>)}</div>}{result?.status === 'success' && <div className="success checkin-result"><strong>CHECK-IN APPROVED</strong><span>{result.attendee_name} · {result.course}</span><small>{result.ticket_number}</small></div>}</div></Shell>
}
