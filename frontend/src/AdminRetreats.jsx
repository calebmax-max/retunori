import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Archive, Copy, Edit3, Save } from 'lucide-react'
import './portal.css'
import { apiErrorMessage } from './apiError'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem("retunori_token"); if (token) config.headers.Authorization = "Bearer " + token; return config })
const dateValue = value => {
  if (!value) return ''
  const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`)
  const year = parsed.getUTCFullYear()
  const month = String(parsed.getUTCMonth() + 1).padStart(2, '0')
  const day = String(parsed.getUTCDate()).padStart(2, '0')
  const hour = String(parsed.getUTCHours()).padStart(2, '0')
  const minute = String(parsed.getUTCMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hour}:${minute}`
}

export default function AdminRetreats() {
  const [items, setItems] = useState([]); const [editing, setEditing] = useState(null); const [status, setStatus] = useState('')
  const load = () => api.get('/admin/retreats').then(r=>setItems(r.data)).catch(e=>setStatus(apiErrorMessage(e, 'Retreats could not be loaded')))
  useEffect(() => { load() }, [])
  const update = async event => {
    event.preventDefault()
    const payload = {
      title: editing.title.trim(),
      description: editing.description.trim(),
      venue: editing.venue.trim(),
      starts_at: editing.starts_at,
      ends_at: editing.ends_at,
      price_kes: editing.is_free ? 0 : Number(editing.price_kes),
      capacity: Number(editing.capacity),
      status: editing.status,
      sales_open: Boolean(editing.sales_open),
      sales_opens_at: editing.sales_opens_at || null,
      sales_closes_at: editing.sales_closes_at || null
    }
    try {
      await api.put(`/admin/retreats/${editing.id}`, payload)
      setStatus(`${editing.title} was updated and saved.`)
      setEditing(null)
      load()
    } catch (e) { setStatus(apiErrorMessage(e, 'Retreat could not be updated')) }
  }
  const action = async (url, message) => { try { await api.post(url); setStatus(message); load() } catch (e) { setStatus(apiErrorMessage(e, 'Retreat action failed')) } }
  const publish = async item => {
    const willPublish = item.status !== 'published'
    try {
      await api.put(`/admin/retreats/${item.id}`, { status: willPublish ? 'published' : 'draft' })
      setStatus(willPublish ? `${item.title} is now published and visible on the public site.` : `${item.title} was moved back to draft.`)
      load()
    } catch (e) { setStatus(apiErrorMessage(e, 'Event publication status could not be updated')) }
  }
  return <section className="page section manage"><div className="eyebrow">ADMINISTRATION</div><h1>Retreat management.</h1><p className="lead">Edit publication, ticket pricing, capacity, sales windows, duplication and archival state.</p>{status && <div className="admin-save-status" role="status" aria-live="polite">{status}</div>}<div className="content-list">{items.map(item=><article className="content-card" key={item.id}><div className="eyebrow">{item.status} · {item.sales_open ? 'SALES OPEN' : 'SALES CLOSED'}</div><h2>{item.title}</h2><p className="muted">{item.venue} · KES {item.price_kes.toLocaleString()} · capacity {item.capacity}</p><div className="export-links">  <button className={item.status === 'published' ? 'button secondary' : 'button primary'} onClick={()=>publish(item)}>{item.status === 'published' ? 'Unpublish' : 'Publish event'}</button><button className="button secondary" onClick={()=>setEditing({...item, starts_at: dateValue(item.starts_at), ends_at: dateValue(item.ends_at), sales_opens_at: dateValue(item.sales_opens_at), sales_closes_at: dateValue(item.sales_closes_at)})}><Edit3 size={14}/> Edit</button><button className="button secondary" onClick={()=>action(`/admin/retreats/${item.id}/duplicate`, 'Retreat duplicated.') }><Copy size={14}/> Duplicate</button><button className="button secondary" onClick={()=>action(`/admin/retreats/${item.id}/archive`, 'Retreat archived.') }><Archive size={14}/> Archive</button></div></article>)}</div>{editing && <form className="dash-card manage-form" onSubmit={update}><h3>Edit {editing.title}</h3>{status && <div className="admin-save-status" role="alert" aria-live="assertive">{status}</div>}<input required value={editing.title} onChange={e=>setEditing({...editing,title:e.target.value})}/><textarea required value={editing.description} onChange={e=>setEditing({...editing,description:e.target.value})}/><input required value={editing.venue} onChange={e=>setEditing({...editing,venue:e.target.value})}/><input required type="datetime-local" value={editing.starts_at} onChange={e=>setEditing({...editing,starts_at:e.target.value})}/><input required type="datetime-local" value={editing.ends_at} onChange={e=>setEditing({...editing,ends_at:e.target.value})}/>  {!editing.is_free && <input required type="number" value={editing.price_kes} onChange={e=>setEditing({...editing,price_kes:e.target.value})}/>}
  <label className="consent"><input type="checkbox" checked={editing.is_free} onChange={e=>setEditing({...editing,is_free:e.target.checked,price_kes:e.target.checked?0:editing.price_kes})}/> Free event</label><input required type="number" value={editing.capacity} onChange={e=>setEditing({...editing,capacity:e.target.value})}/><select value={editing.status} onChange={e=>setEditing({...editing,status:e.target.value})}><option value="draft">Draft</option><option value="published">Published</option><option value="scheduled">Scheduled</option><option value="archived">Archived</option></select><label className="consent"><input type="checkbox" checked={editing.sales_open} onChange={e=>setEditing({...editing,sales_open:e.target.checked})}/> Sales open</label><input type="datetime-local" value={editing.sales_opens_at} onChange={e=>setEditing({...editing,sales_opens_at:e.target.value})} /><input type="datetime-local" value={editing.sales_closes_at} onChange={e=>setEditing({...editing,sales_closes_at:e.target.value})} /><button className="button primary">Save changes <Save size={15}/></button></form>}</section>
}
