import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Bell } from 'lucide-react'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })

export default function AdminNotifications() {
  const [items, setItems] = useState([]); const [status, setStatus] = useState(''); const [expanded, setExpanded] = useState(null); const [filter, setFilter] = useState({ kind: '', unread_only: false })
  const load = () => api.get('/admin/notifications', { params: filter }).then(r => setItems(r.data)).catch(() => setStatus('Notifications could not be loaded'))
  useEffect(() => { load() }, [filter.kind, filter.unread_only])
  const read = async item => { try { await api.post(`/admin/notifications/${item.id}/read`); setExpanded(expanded === item.id ? null : item.id); load() } catch (e) { setStatus(e.response?.data?.detail || 'Notification could not be opened') } }
  const action = async (url, method = 'post') => { try { await api({ url, method }); load() } catch (e) { setStatus(e.response?.data?.detail || 'Notification action failed') } }
  return <section className="page section manage"><div className="eyebrow"><Bell size={14}/> ADMINISTRATION</div><h1>Notification centre.</h1><p className="lead">Review operational events and open the full message without deleting the underlying record.</p>{status && <p className="error">{status}</p>}<div className="report-filter"><input placeholder="Filter by notification type" value={filter.kind} onChange={e=>setFilter({...filter,kind:e.target.value})}/><label className="consent"><input type="checkbox" checked={filter.unread_only} onChange={e=>setFilter({...filter,unread_only:e.target.checked})}/> Unread only</label></div><div className="dash-card activity-card"><div className="export-links"><button className="button secondary" onClick={()=>action('/admin/notifications/read-all')}>Mark all read</button></div>{items.length ? items.map(item=><div className="report-row notification-row" key={item.id}><span><strong>{item.title}</strong><small>{item.kind} · {new Date(item.created_at).toLocaleString()} · {item.is_read ? 'Read' : 'Unread'}{item.is_archived ? ' · Archived' : ''}</small>{expanded === item.id && <small className="notification-body">{item.body}</small>}</span><span className="export-links"><button className="button secondary" onClick={()=>read(item)}>{expanded === item.id ? 'Close' : 'Read'}</button><button className="button secondary" onClick={()=>action(`/admin/notifications/${item.id}/archive`)}>Archive</button><button className="button secondary" onClick={()=>action(`/admin/notifications/${item.id}`, 'delete')}>Delete</button></span></div>) : <p className="muted">No notifications yet.</p>}</div></section>
}
