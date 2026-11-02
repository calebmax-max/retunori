import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Search, Save } from 'lucide-react'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })

export default function AdminAttendees() {
  const [name, setName] = useState(''); const [items, setItems] = useState([]); const [status, setStatus] = useState(''); const [editing, setEditing] = useState(null)
  const search = () => api.get('/admin/attendees', { params: { name } }).then(r=>setItems(r.data)).catch(e=>setStatus(e.response?.data?.detail || 'Attendees could not be loaded'))
  useEffect(() => { search() }, [])
  const save = async event => { event.preventDefault(); try { await api.put(`/admin/attendees/${editing.id}`, editing); setStatus('Attendee details corrected and logged.'); setEditing(null); search() } catch (e) { setStatus(e.response?.data?.detail || 'Attendee details could not be saved') } }
  return <section className="page section manage"><div className="eyebrow">ADMINISTRATION</div><h1>Paid attendees.</h1><p className="lead">Search attendee records by name. Corrections are audited and do not rewrite historical ticket snapshots.</p><form className="report-filter" onSubmit={e=>{e.preventDefault();search()}}><input placeholder="Search attendee name" value={name} onChange={e=>setName(e.target.value)}/><button className="button secondary"><Search size={15}/> Search</button></form>{status && <p className="muted form-status">{status}</p>}<div className="content-list">{items.length ? items.map(item=><article className="content-card" key={item.id}><h2>{item.full_name}</h2><p className="muted">{item.email} · {item.phone} · {item.course_of_study}</p><p><strong>{item.tickets.length}</strong> ticket(s) · <strong>{item.payments.filter(payment=>payment.status === 'successful').length}</strong> successful payment(s)</p>{item.tickets.map(ticket=><div className="report-row" key={ticket.ticket_number}><span>{ticket.retreat_title}<small>{ticket.ticket_number} · {ticket.course}</small></span><strong>Ticket</strong></div>)}<button className="button secondary" onClick={()=>setEditing(item)}>Correct details</button></article>) : <p className="muted">No attendee records match this search.</p>}</div>{editing && <div className="dash-card manage-form"><h3>Correct {editing.full_name}</h3><form onSubmit={save}><input required value={editing.full_name} onChange={e=>setEditing({...editing,full_name:e.target.value})}/><input required value={editing.phone} onChange={e=>setEditing({...editing,phone:e.target.value})}/><input required value={editing.course_of_study} onChange={e=>setEditing({...editing,course_of_study:e.target.value})}/><button className="button primary">Save correction <Save size={15}/></button></form></div>}</section>
}
