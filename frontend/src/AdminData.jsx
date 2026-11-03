import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Archive, Download, FileText, RefreshCw } from 'lucide-react'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })

export function AdminPayments() {
  const [status, setStatus] = useState(''); const [items, setItems] = useState([])
  const load = () => api.get('/admin/payments', { params: status ? { status } : {} }).then(r => setItems(r.data)).catch(e => setStatus(e.response?.data?.detail || 'Payments could not be loaded'))
  useEffect(() => { load() }, [status])
  return <section className="page section manage"><div className="eyebrow">ADMINISTRATION</div><h1>Payment records.</h1><p className="lead">Read-only payment operations. Only verified Daraja callbacks create tickets.</p><select className="report-filter" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="successful">Successful</option><option value="failed">Failed</option></select>{status && <p className="error">{status}</p>}<div className="dash-card activity-card">{items.length ? items.map(item => <div className="report-row" key={item.id}><span><strong>{item.attendee_name} · {item.retreat_title}</strong><small>{item.transaction_reference} · {item.phone_number} · {new Date(item.requested_at).toLocaleString()}</small></span><span><strong>{item.status}</strong><small>KES {(item.paid_amount ?? item.expected_amount).toLocaleString()}{item.receipt ? ` · ${item.receipt}` : ''}</small></span></div>) : <p className="muted">No payment records found.</p>}</div></section>
}

export function AdminTickets() {
  const [items, setItems] = useState([]); const [retreats, setRetreats] = useState([]); const [retreatId, setRetreatId] = useState(''); const [status, setStatus] = useState('')
  const load = () => api.get('/admin/tickets', { params: retreatId ? { retreat_id: retreatId } : {} }).then(r=>setItems(r.data)).catch(e=>setStatus(e.response?.data?.detail || 'Tickets could not be loaded'))
  useEffect(() => { api.get('/admin/retreats').then(r=>setRetreats(r.data)).catch(()=>setStatus('Retreats could not be loaded')) }, []); useEffect(() => { load() }, [retreatId])
  return <section className="page section manage"><div className="eyebrow">ADMINISTRATION</div><h1>Issued tickets.</h1><p className="lead">Historical ticket snapshots remain unchanged when retreat settings are edited.</p><select className="report-filter" value={retreatId} onChange={e=>setRetreatId(e.target.value)}><option value="">All retreats</option>{retreats.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select>{status && <p className="error">{status}</p>}<div className="dash-card activity-card">{items.length ? items.map(item=><div className="report-row" key={item.ticket_number}><span><strong>{item.ticket_number} · {item.attendee_name}</strong><small>{item.retreat_title} · {item.course} · {item.receipt || 'No receipt'}</small></span><span><strong>{item.payment_status}</strong><small>{item.checked_in_at ? `Checked in ${new Date(item.checked_in_at).toLocaleString()}` : 'Not checked in'}</small></span></div>) : <p className="muted">No issued tickets found.</p>}</div></section>
}

export function AdminBackups() {
  const [items, setItems] = useState([]); const [status, setStatus] = useState('')
  const load = () => api.get('/admin/backups').then(r=>setItems(r.data)).catch(e=>setStatus(e.response?.data?.detail || 'Backups could not be loaded'))
  useEffect(() => { load() }, [])
  const create = async () => { try { await api.post('/admin/backups'); setStatus('Backup created.'); load() } catch (e) { setStatus(e.response?.data?.detail || 'Backup could not be created') } }
  const download = async item => { try { const response = await api.get(`/admin/backups/${item.id}/download`, { responseType: 'blob' }); const url = window.URL.createObjectURL(response.data); const link = document.createElement('a'); link.href = url; link.download = item.filename; document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url) } catch { setStatus('The backup could not be downloaded.') } }
  return <section className="page section manage"><div className="eyebrow"><Archive size={14}/> ADMINISTRATION</div><h1>Backup management.</h1><p className="lead">Backups are protected behind administrator authentication. Restore operations create a safety copy first.</p><button className="button primary" onClick={create}><RefreshCw size={15}/> Create backup</button>{status && <p className="muted form-status">{status}</p>}<div className="dash-card activity-card">{items.length ? items.map(item=><div className="report-row" key={item.id}><span><strong>{item.filename}</strong><small>{new Date(item.created_at).toLocaleString()} · {item.status}</small></span><button type="button" className="icon-link" onClick={() => download(item)}><Download size={15}/> Download</button></div>) : <p className="muted">No backups recorded yet.</p>}</div></section>
}
