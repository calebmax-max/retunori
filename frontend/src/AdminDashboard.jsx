import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { BarChart3, CalendarDays, CreditCard, Download, FileText, Image, LayoutDashboard, Menu, Settings, Ticket, Users, X } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
const links = [['/admin/manage', 'Create retreat'], ['/admin/retreats', 'Retreats'], ['/admin/media', 'Media'], ['/admin/payments', 'Payments'], ['/admin/tickets', 'Tickets'], ['/admin/attendees', 'Attendees'], ['/admin/staff', 'Staff'], ['/admin/publishing', 'Publishing'], ['/admin/content', 'Content and SEO'], ['/admin/notifications', 'Notifications'], ['/admin/backups', 'Backups']]

export default function AdminDashboard() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState({}); const [report, setReport] = useState({}); const [dates, setDates] = useState({ start: '', end: '' }); const [error, setError] = useState(''); const [menuOpen, setMenuOpen] = useState(false)
  const load = () => { const params = {}; if (dates.start) params.start = new Date(dates.start).toISOString(); if (dates.end) params.end = new Date(dates.end).toISOString(); Promise.all([api.get('/admin/overview'), api.get('/admin/reports', { params })]).then(([a, b]) => { setOverview(a.data || {}); setReport(b.data || {}); setError('') }).catch(e => setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Admin reports could not be loaded')) }
  useEffect(() => { load(); const timer = window.setInterval(() => { if (!document.hidden) load() }, 60000); return () => window.clearInterval(timer) }, [dates.start, dates.end])
  const rows = Array.isArray(report.retreats) ? report.retreats : []; const courses = Array.isArray(report.by_course) ? report.by_course : []
  const navIcons = [LayoutDashboard, CalendarDays, Image, CreditCard, Ticket, Users, Users, FileText, Settings, FileText, BarChart3]
  const signOut = () => {
    localStorage.removeItem('retunori_token')
    localStorage.removeItem('retunori_user')
    window.dispatchEvent(new Event('retunori-auth-changed'))
    navigate('/login')
  }
  return <main className="admin-shell">
    <aside className="admin-sidebar">
      <Link to="/" className="admin-brand"><span className="brand-mark">R</span><span>RETUNORI</span></Link>
      <button className="admin-menu-toggle" type="button" aria-label="Toggle admin navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>
        {menuOpen ? <X size={21}/> : <Menu size={21}/>}
      </button>
      <nav className={menuOpen ? 'admin-nav open' : 'admin-nav'} aria-label="Administration navigation" onClick={() => setMenuOpen(false)}>
        {links.map(([href, label], index) => { const Icon = navIcons[index]; return <Link className={index === 0 ? 'active' : ''} key={href} to={href}><Icon size={18}/><span>{label}</span></Link> })}
      </nav>
      <Link className="admin-view-site" to="/">View public site <span>↗</span></Link>
    </aside>
    <section className="admin-workspace">
      <header className="admin-topbar"><div><span>Admin workspace</span><strong>Operations overview</strong></div><div className="admin-account-actions"><button className="admin-avatar" aria-label="Administrator profile">AD</button><button className="admin-signout" type="button" onClick={signOut}>Sign out</button></div></header>
      <div className="admin-content">
        <div className="admin-page-heading"><div><div className="eyebrow">ADMINISTRATION</div><h1>Good morning.</h1><p>Here is what is happening across RETUNORI.</p></div><Link className="button primary" to="/admin/manage">Create retreat</Link></div>
        {error && <p className="error admin-error">{error}</p>}
        <form className="admin-filter" onSubmit={e => { e.preventDefault(); load() }}><span>Reporting period</span><input aria-label="Start date" type="datetime-local" value={dates.start} onChange={e => setDates({ ...dates, start: e.target.value })}/><input aria-label="End date" type="datetime-local" value={dates.end} onChange={e => setDates({ ...dates, end: e.target.value })}/><button className="button secondary">Apply</button></form>
        <div className="admin-metrics">{[['Revenue', `KES ${Number(overview.revenue_kes || 0).toLocaleString()}`, '+12.8%'], ['Registrations', overview.registrations, 'New bookings'], ['Paid attendees', overview.paid_attendees, 'Confirmed'], ['Remaining capacity', overview.remaining_capacity, 'Across events']].map(([label, value, note]) => <div className="admin-metric" key={label}><span>{label}</span><strong>{value ?? '—'}</strong><small>{note}</small></div>)}</div>
        <div className="admin-panels">
          <div className="admin-panel capacity-panel"><div className="admin-panel-head"><div><span>EVENT PERFORMANCE</span><h2>Capacity</h2></div><Link className="icon-link" to="/admin/retreats">View all</Link></div>{rows.map(row => <div className="capacity-row" key={row.id}><div><strong>{row.title}</strong><span>{row.tickets_sold} sold · {row.remaining} remaining</span></div><div className="capacity-track"><i style={{ width: `${row.capacity ? Math.min(100, (row.tickets_sold / row.capacity) * 100) : 0}%` }}/></div><b>{row.capacity}</b></div>)}</div>
          <div className="admin-panel"><div className="admin-panel-head"><div><span>ATTENDANCE</span><h2>Course mix</h2></div></div>{courses.map(row => <div className="course-row" key={row.course}><span>{row.course}</span><strong>{row.attendees}</strong></div>)}</div>
        </div>
        <div className="admin-actions"><span>Exports</span><a href="/api/admin/reports/export.xlsx"><Download size={16}/> Excel report</a><a href="/api/admin/reports/export.pdf"><Download size={16}/> PDF report</a></div>
      </div>
    </section>
  </main>
}
