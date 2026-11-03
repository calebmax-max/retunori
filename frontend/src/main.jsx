import React, { lazy, Suspense, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CalendarDays, Check, ChevronRight, LayoutDashboard, LogIn, MapPin, Menu, ShieldCheck, Sparkles, Ticket, X } from 'lucide-react'
import axios from 'axios'
import './styles.css'
import './experience.css'
import { ContactPage, LegalPage } from './PublicPages'

const AdminDashboard = lazy(() => import('./AdminDashboard'))
const AdminManage = lazy(() => import('./AdminManage'))
const AdminContent = lazy(() => import('./AdminContent'))
const AdminMedia = lazy(() => import('./AdminMedia'))
const AdminNotifications = lazy(() => import('./AdminNotifications'))
const AdminPublishing = lazy(() => import('./AdminPublishing'))
const AdminRetreats = lazy(() => import('./AdminRetreats'))
const AdminAttendees = lazy(() => import('./AdminAttendees'))
const PurchaseFlow = lazy(() => import('./PurchaseFlow'))
const RetreatDetail = lazy(() => import('./RetreatDetail'))
const AccountPage = lazy(() => import('./AttendeeDashboard').then(module => ({ default: module.AccountPage })))
const AttendeeDashboard = lazy(() => import('./AttendeeDashboard').then(module => ({ default: module.AttendeeDashboard })))
const AdminCourseAssignments = lazy(() => import('./AdminOperations').then(module => ({ default: module.AdminCourseAssignments })))
const AdminStaff = lazy(() => import('./AdminOperations').then(module => ({ default: module.AdminStaff })))
const StaffDashboard = lazy(() => import('./OperationsDashboards').then(module => ({ default: module.StaffDashboard })))
const AdminBackups = lazy(() => import('./AdminData').then(module => ({ default: module.AdminBackups })))
const AdminPayments = lazy(() => import('./AdminData').then(module => ({ default: module.AdminPayments })))
const AdminTickets = lazy(() => import('./AdminData').then(module => ({ default: module.AdminTickets })))

const api = axios.create({ baseURL: '/api' })

const wallClockDate = value => {
  if (!value) return null
  const match = String(value).trim().match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (!match) return null
  const [, year, month, day, hour, minute] = match
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour) - 3, Number(minute)))
}

const registrationDeadline = value => {
  const deadline = wallClockDate(value)
  if (!deadline) return ''
  return deadline.toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC'
  })
}

const registrationIsOpen = retreat => retreat?.sales_open && (!retreat.sales_closes_at || wallClockDate(retreat.sales_closes_at)?.getTime() > Date.now())
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use(response => response, error => { const detail = error.response?.data?.detail; if (Array.isArray(detail)) error.response.data.detail = detail.map(item => item.msg || 'Invalid value').join('; '); return Promise.reject(error) })
const platformHeroImage = 'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1200&q=70'
const platformCommunityImage = 'https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=800&q=70'

class AppErrorBoundary extends React.Component {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) return <section className="page section"><h1>Something went wrong.</h1><p className="muted">The page could not display this response. Refresh and try again.</p><button className="button primary" onClick={() => window.location.reload()}>Refresh page</button></section>
    return this.props.children
  }
}

function Header() { const [open, setOpen] = useState(false); const [user, setUser] = useState(() => { try { return JSON.parse(localStorage.getItem('retunori_user') || 'null') } catch { return null } }); const navigate = useNavigate(); const location = useLocation(); useEffect(() => { const refresh = () => { try { setUser(JSON.parse(localStorage.getItem('retunori_user') || 'null')) } catch { setUser(null) } }; refresh(); window.addEventListener('retunori-auth-changed', refresh); return () => window.removeEventListener('retunori-auth-changed', refresh) }, [location.pathname]); const signOut = () => { localStorage.removeItem('retunori_token'); localStorage.removeItem('retunori_user'); window.dispatchEvent(new Event('retunori-auth-changed')); setOpen(false); navigate('/') }; return <header className="header"><div className="header-inner"><Link to="/" className="brand" onClick={() => setOpen(false)}><span className="brand-mark">R</span><span>RETUNORI</span></Link><button className="menu" aria-label="Toggle navigation" onClick={() => setOpen(!open)}>{open ? <X/> : <Menu/>}</button><nav className={open ? 'nav open' : 'nav'}><Link to="/retreats" onClick={() => setOpen(false)}>Explore events</Link><Link to="/contact" onClick={() => setOpen(false)}>Contact</Link>{user ? <button className="nav-login nav-signout" onClick={signOut}>Sign out</button> : <Link className="nav-login" to="/login" onClick={() => setOpen(false)}><LogIn size={16}/> Sign in</Link>}<Link className="nav-cta" to="/retreats" onClick={() => setOpen(false)}>Find your next experience <ArrowRight size={15}/></Link></nav></div></header> }
const adminNavigation = [
  ['/admin/manage', 'Create event'],
  ['/admin/retreats', 'Events'],
  ['/admin/media', 'Media'],
  ['/admin/payments', 'Payments'],
  ['/admin/tickets', 'Tickets'],
  ['/admin/attendees', 'Attendees'],
  ['/admin/staff', 'Staff'],
  ['/admin/course-options', 'Course options'],
  ['/admin/publishing', 'Publishing'],
  ['/admin/content', 'Content & SEO'],
  ['/admin/notifications', 'Notifications'],
  ['/admin/backups', 'Backups']
]

function AdminSectionShell({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const signOut = () => {
    localStorage.removeItem('retunori_token')
    localStorage.removeItem('retunori_user')
    window.dispatchEvent(new Event('retunori-auth-changed'))
    navigate('/login')
  }
  return <main className="admin-shell admin-section-shell">
    <aside className="admin-sidebar">
      <Link to="/admin" className="admin-brand"><span className="brand-mark">R</span><span>RETUNORI</span></Link>
      <button className="admin-menu-toggle" type="button" aria-label="Toggle admin navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>
        {menuOpen ? <X size={21}/> : <Menu size={21}/>}
      </button>
      <nav className={menuOpen ? 'admin-nav open' : 'admin-nav'} aria-label="Administration navigation" onClick={() => setMenuOpen(false)}>
        <Link to="/admin"><LayoutDashboard size={18}/><span>Overview</span></Link>
        {adminNavigation.map(([href, label]) => <Link className={location.pathname === href ? 'active' : ''} key={href} to={href}><span>{label}</span></Link>)}
      </nav>
      <Link className="admin-view-site" to="/">View public site <span>↗</span></Link>
    </aside>
    <section className="admin-workspace">
      <header className="admin-topbar"><Link className="admin-back" to="/admin"><ArrowLeft size={15}/> Back to overview</Link><div className="admin-account-actions"><button className="admin-avatar" aria-label="Administrator profile">AD</button><button className="admin-signout" type="button" onClick={signOut}>Sign out</button></div></header>
      <div className="admin-section-content">{children}</div>
    </section>
  </main>
}

function Layout({ children }) {
  const location = useLocation()
  const isAdmin = location.pathname === '/admin' || location.pathname.startsWith('/admin/')
  if (location.pathname === '/admin') return <main>{children}</main>
  if (isAdmin) return <AdminSectionShell>{children}</AdminSectionShell>
  return <><Header/><main>{children}</main><footer><div className="brand"><span className="brand-mark">R</span><span>RETUNORI</span></div><span>Retreats · Experiences · Connections</span><span>© 2026 RETUNORI</span></footer></>
}
function RetreatCard({ retreat, tickets = [] }) { const image = retreat.images?.[0]?.url || retreat.poster_url; const isOpen = registrationIsOpen(retreat); const hasTicket = tickets.some(ticket => ticket.retreat_title === retreat.title); return <article className="retreat-card"><div className="poster">{image && <img className="poster-image" src={image} alt={retreat.images?.[0]?.alt_text || retreat.title} loading="lazy" decoding="async" onError={event => { event.currentTarget.style.display = 'none' }}/>}<div className="poster-glow"/><span>RETUNORI<br/><b>{new Date(retreat.starts_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }).toUpperCase()}</b></span></div><div className="card-body"><div className="eyebrow">{hasTicket ? 'TICKET BOOKED' : retreat.remaining_capacity === 0 ? 'SOLD OUT' : isOpen ? 'REGISTRATION OPEN' : 'REGISTRATION CLOSED'}</div><h3>{retreat.title}</h3><p className="muted"><CalendarDays size={15}/> {new Date(retreat.starts_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</p><p className="muted"><MapPin size={15}/> {retreat.venue}</p>{retreat.sales_closes_at && <p className="registration-deadline">Registration {isOpen ? 'open until' : 'closed on'} {registrationDeadline(retreat.sales_closes_at)}</p>}<p className="muted availability">{hasTicket ? 'Your place is confirmed' : `${retreat.remaining_capacity} places remaining`}</p><div className="card-footer"><strong>KES {retreat.is_free ? 'FREE' : retreat.price_kes.toLocaleString()}</strong><Link to={`/retreats/${retreat.slug}`} className="icon-link">{hasTicket ? 'View ticket' : 'Explore'} <ArrowRight size={16}/></Link></div></div></article> }
function EventCountdown({ target }) { const [left, setLeft] = useState(Math.max(0, new Date(target).getTime() - Date.now())); useEffect(() => { const timer = window.setInterval(() => setLeft(Math.max(0, new Date(target).getTime() - Date.now())), 1000); return () => window.clearInterval(timer) }, [target]); const days = Math.floor(left / 86400000); const hours = Math.floor(left / 3600000) % 24; const minutes = Math.floor(left / 60000) % 60; const seconds = Math.floor(left / 1000) % 60; return <div className="event-countdown"><span><strong>{days}</strong><small>Days</small></span><span><strong>{String(hours).padStart(2, '0')}</strong><small>Hours</small></span><span><strong>{String(minutes).padStart(2, '0')}</strong><small>Minutes</small></span><span><strong>{String(seconds).padStart(2, '0')}</strong><small>Seconds</small></span></div> }
function Home() {
  const [retreats, setRetreats] = useState([]); const [home, setHome] = useState(null); const [tickets, setTickets] = useState([]); const [now, setNow] = useState(Date.now())
  useEffect(() => { Promise.all([api.get('/retreats'), api.get('/homepage')]).then(([retreatResponse, homeResponse]) => { setRetreats(retreatResponse.data); setHome(homeResponse.data) }).catch(() => {}) ; if (localStorage.getItem('retunori_token')) api.get('/me/tickets').then(response => setTickets(response.data)).catch(() => {}) }, [])
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 30000); return () => window.clearInterval(timer) }, [])
  const featured = home?.featured_retreats?.length ? home.featured_retreats : retreats
  const upcomingRetreats = [...retreats].filter(item => new Date(item.ends_at).getTime() >= now).sort((a, b) => {
    const aTime = new Date(a.starts_at).getTime() <= now ? -1 : new Date(a.starts_at).getTime()
    const bTime = new Date(b.starts_at).getTime() <= now ? -1 : new Date(b.starts_at).getTime()
    return aTime - bTime
  })
  const heroRetreat = upcomingRetreats[0]
  return <>
    <section className="event-hero">
      <div className="event-hero-image"><img src={heroRetreat?.images?.[0]?.url || platformHeroImage} alt={heroRetreat?.title || 'People connecting outdoors at a RETUNORI event'}/><div className="event-hero-shade"/></div>
      <div className="event-hero-content">
        <div className="eyebrow"><Sparkles size={15}/> EVENTS · EXPERIENCES · CONNECTIONS</div>
        <p className="event-kicker">Make time for what matters</p>
        <h1>{heroRetreat?.title || home?.content?.headline || 'Events that bring people closer.'}</h1>
        <p className="event-meta">{heroRetreat ? `${heroRetreat.venue} · ${new Date(heroRetreat.starts_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}` : 'Meaningful gatherings across Kenya'}</p>
        <p className="event-intro">{home?.content?.introduction || 'Thoughtful events and experiences for people seeking connection, perspective, and a little more space to breathe.'}</p>
        <div className="event-actions"><Link className="button primary" to={heroRetreat ? `/retreats/${heroRetreat.slug}` : '/retreats'}>{heroRetreat ? 'View this experience' : 'Explore events'} <ArrowRight size={17}/></Link><Link className="event-outline" to="/contact">Talk to our team</Link></div>
        {heroRetreat && <EventCountdown target={heroRetreat.starts_at}/>}
      </div>
    </section>
    <section className="about-event section">
      <div className="about-collage">
        <div className="about-collage-main"><img src={platformCommunityImage} alt="Friends sharing a meaningful moment at a RETUNORI gathering"/></div>
        <div className="about-collage-secondary"><img src={platformHeroImage} alt="RETUNORI community outdoors"/></div>
        <div className="about-badge">R<br/><small>RETUNORI</small></div>
      </div>
      <div className="about-copy"><div className="eyebrow">ABOUT RETUNORI</div><h2>Gather well.<br/><em>Leave changed.</em></h2><p>RETUNORI creates room for meaningful events, honest conversations, and experiences that stay with you long after the day ends.</p><p>From intimate gatherings to vibrant community moments, every event is designed around connection, presence, and a sense of belonging.</p><Link className="button secondary" to="/about">Discover our story <ArrowRight size={16}/></Link></div>
    </section>
    <section className="section event-listing">
      <div className="section-heading"><div><div className="eyebrow">THE CALENDAR</div><h2>Upcoming events</h2></div><Link className="text-link" to="/retreats">View all <ChevronRight size={16}/></Link></div>
      <div className="retreat-grid">{featured.length ? featured.map(r => <RetreatCard key={r.slug} retreat={r} tickets={tickets}/>) : retreats.slice(0, 3).map(r => <RetreatCard key={r.slug} retreat={r} tickets={tickets}/>)}</div>
      {!(featured.length || retreats.length) && <p className="muted">New events and experiences will appear here soon.</p>}
    </section>
    <section className="event-cta"><div className="eyebrow">YOUR NEXT GOOD MOMENT</div><h2>Come as you are.<br/><em>Find your people.</em></h2><Link className="button primary" to="/retreats">Explore all events <ArrowRight size={17}/></Link></section>
  </>
}
function Retreats() { const [retreats, setRetreats] = useState([]); const [tickets, setTickets] = useState([]); const [query, setQuery] = useState(''); useEffect(() => { api.get('/retreats').then(response => setRetreats(response.data)).catch(() => {}); if (localStorage.getItem('retunori_token')) api.get('/me/tickets').then(response => setTickets(response.data)).catch(() => {}) }, []); const visible = retreats.filter(item => `${item.title} ${item.venue}`.toLowerCase().includes(query.toLowerCase())); return <section className="page section events-page"><div className="events-heading"><div><div className="eyebrow">THE RETUNORI CALENDAR</div><h1>Find your next<br/><em>good pause.</em></h1><p className="lead">Choose an experience that gives you room to breathe, reflect, and connect.</p></div><div className="events-count"><strong>{retreats.length}</strong><span>upcoming experiences</span></div></div><div className="events-toolbar"><label><span>Search experiences</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search by title or location"/></label><span>{visible.length} results</span></div><div className="retreat-grid">{visible.map(r => <RetreatCard key={r.slug} retreat={r} tickets={tickets}/>)}</div>{visible.length === 0 && <p className="muted events-empty">No experiences match your search. Try another location or title.</p>}</section> }
function Detail() { const { slug } = useParams(); const [retreat, setRetreat] = useState(null); const [error, setError] = useState(''); useEffect(() => { api.get(`/retreats/${slug}`).then(r => setRetreat(r.data)).catch(e => setError(e.response?.data?.detail || 'Retreat not found')) }, [slug]); if (error) return <section className="page section"><h1>Retreat unavailable.</h1><p className="muted">{error}</p><Link className="text-link" to="/retreats">Browse retreats</Link></section>; if (!retreat) return <div className="loading">Loading retreat…</div>; return <section className="detail page section"><Link className="text-link" to="/retreats">← All retreats</Link><div className="detail-grid"><div className="retreat-gallery">{retreat.images?.length ? retreat.images.map(image => <img key={image.id} src={image.url} alt={image.alt_text} loading="lazy"/>) : <div className="poster large"><span>RETUNORI<br/><b>{retreat.title}</b></span></div>}</div><div><div className="eyebrow">{retreat.sales_open ? 'REGISTRATION OPEN' : 'COMING SOON'}</div><h1>{retreat.title}</h1><p className="lead">{retreat.description}</p><div className="facts"><span><CalendarDays/> {new Date(retreat.starts_at).toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric'})}</span><span><MapPin/> {retreat.venue}</span><span><Ticket/> KES {retreat.price_kes.toLocaleString()}</span></div><Link to={`/purchase?retreat=${retreat.id}`} className="button primary">Get your ticket <ArrowRight size={17}/></Link></div></div></section> }
function Login({ register = false }) { const navigate = useNavigate(); const [error, setError] = useState(''); const [form, setForm] = useState({ full_name:'', email:'', phone:'', course_of_study:'', password:'' }); const submit = async e => { e.preventDefault(); try { const r = await api.post(register ? '/auth/register' : '/auth/login', form); localStorage.setItem('retunori_token', r.data.access_token); localStorage.setItem('retunori_user', JSON.stringify(r.data.user)); navigate('/dashboard') } catch (e) { setError(e.response?.data?.detail || 'Something went wrong. Please try again.') } }; return <section className="auth page"><div className="auth-card"><div className="eyebrow">{register ? 'JOIN RETUNORI' : 'WELCOME BACK'}</div><h1>{register ? 'Begin your next chapter.' : 'Good to see you.'}</h1><p className="muted">{register ? 'Create an account to reserve your place.' : 'Sign in to access your retreats and tickets.'}</p><form onSubmit={submit}>{register && <input placeholder="Full name" required onChange={e=>setForm({...form,full_name:e.target.value})}/>}<input type="email" placeholder="Email address" required onChange={e=>setForm({...form,email:e.target.value})}/>{register && <><input placeholder="Phone number" required onChange={e=>setForm({...form,phone:e.target.value})}/><input placeholder="Course of study" required onChange={e=>setForm({...form,course_of_study:e.target.value})}/></>}<input type="password" placeholder="Password" required minLength="8" onChange={e=>setForm({...form,password:e.target.value})}/>{error && <div className="error">{error}</div>}<button className="button primary" type="submit">{register ? 'Create account' : 'Sign in'} <ArrowRight size={17}/></button></form>{!register && <p className="switch"><Link to="/reset-password">Forgot your password?</Link></p>}<p className="switch">{register ? 'Already have an account?' : 'New to RETUNORI?'} <Link to={register ? '/login' : '/register'}>{register ? 'Sign in' : 'Create an account'}</Link></p></div></section> }
function AboutPage() {
  return <>
    <section className="about-story-hero">
      <div>
        <div className="eyebrow">OUR STORY</div>
        <h1>Life changes when we gather with intention.</h1>
        <p>RETUNORI creates thoughtful experiences where people can pause, connect, and return to everyday life with fresh perspective.</p>
      </div>
      <div className="about-story-mark" aria-hidden="true">R</div>
    </section>
    <section className="about-story-section">
      <div className="about-story-label">WHY RETUNORI EXISTS</div>
      <div>
        <h2>We believe meaningful moments should feel within reach.</h2>
        <p>Our name reflects a simple idea: to return with more—more clarity, stronger connections, and memories that continue long after an event ends.</p>
        <p>We bring people together through carefully planned retreats, workshops, and community experiences rooted in presence, honesty, and belonging.</p>
      </div>
    </section>
    <section className="about-values">
      <article><span>01</span><h3>Presence</h3><p>We create space to slow down, listen closely, and be fully where you are.</p></article>
      <article><span>02</span><h3>Connection</h3><p>Every experience is designed to turn strangers into a welcoming community.</p></article>
      <article><span>03</span><h3>Growth</h3><p>We help people leave with perspective, practical inspiration, and renewed energy.</p></article>
    </section>
    <section className="about-story-cta">
      <div className="eyebrow">YOUR NEXT GOOD MOMENT</div>
      <h2>Find the experience that meets you here.</h2>
      <Link className="button primary" to="/retreats">Explore our events <ArrowRight size={17}/></Link>
    </section>
  </>
}
function PasswordReset() { const params = new URLSearchParams(window.location.search); const token = params.get('token') || ''; const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [message, setMessage] = useState(''); const [error, setError] = useState(''); const request = async e => { e.preventDefault(); setError(''); try { const response = await api.post('/auth/password-reset/request', { email }); setMessage(response.data.message) } catch (e) { setError(e.response?.data?.detail || 'Unable to request a reset link') } }; const confirm = async e => { e.preventDefault(); setError(''); try { const response = await api.post('/auth/password-reset/confirm', { token, password }); setMessage(response.data.message) } catch (e) { setError(e.response?.data?.detail || 'This reset link is invalid or expired') } }; return <section className="auth page"><div className="auth-card"><div className="eyebrow">ACCOUNT SECURITY</div><h1>{token ? 'Choose a new password.' : 'Reset your password.'}</h1><p className="muted">{token ? 'This secure link expires after 30 minutes and can only be used once.' : 'We will send a time-limited reset link to your registered email.'}</p><form onSubmit={token ? confirm : request}>{token ? <input type="password" minLength="8" required placeholder="New password" value={password} onChange={e=>setPassword(e.target.value)}/> : <input type="email" required placeholder="Email address" value={email} onChange={e=>setEmail(e.target.value)}/>} {error && <div className="error">{error}</div>}{message && <div className="success">{message}</div>}<button className="button primary" type="submit">{token ? 'Update password' : 'Send reset link'} <ArrowRight size={17}/></button></form><p className="switch"><Link to="/login">Return to sign in</Link></p></div></section> }
function RegistrationPage() { const navigate = useNavigate(); const [courses, setCourses] = useState([]); const [form, setForm] = useState({ full_name:'', email:'', phone:'', course_of_study:'', password:'' }); const [error, setError] = useState(''); useEffect(() => { api.get('/courses').then(r => setCourses(r.data)).catch(() => setError('Course options could not be loaded')) }, []); const submit = async e => { e.preventDefault(); setError(''); try { const response = await api.post('/auth/register', form); localStorage.setItem('retunori_token', response.data.access_token); localStorage.setItem('retunori_user', JSON.stringify(response.data.user)); navigate('/purchase') } catch (e) { setError(e.response?.data?.detail || 'Account creation failed') } }; return <section className="auth page"><div className="auth-card"><div className="eyebrow">JOIN RETUNORI</div><h1>Begin your next chapter.</h1><p className="muted">Create an account to reserve your place.</p><form onSubmit={submit}><input placeholder="Full name" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/><input type="email" placeholder="Email address" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><input placeholder="Phone number" required value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/><select required value={form.course_of_study} onChange={e=>setForm({...form,course_of_study:e.target.value})}><option value="">Select course of study</option>{courses.map(course => <option key={course.id} value={course.name}>{course.name}</option>)}</select><input type="password" placeholder="Password" required minLength="8" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>{error && <div className="error">{error}</div>}<label className="consent"><input type="checkbox" required/> I agree to the <Link to="/terms">Terms of Service</Link> and <Link to="/privacy">Privacy Policy</Link>.</label><button className="button primary" type="submit">Create account <ArrowRight size={17}/></button></form><p className="switch">Already have an account? <Link to="/login">Sign in</Link></p></div></section> }
function Dashboard() { const user = JSON.parse(localStorage.getItem('retunori_user') || 'null'); if (!user) return <Navigate to="/login"/>; return <section className="page section dashboard"><div className="eyebrow">YOUR RETUNORI</div><h1>Welcome, {user.full_name?.split(' ')[0] || 'there'}.</h1><div className="dashboard-grid"><div className="dash-card"><Ticket/><h3>Your tickets</h3><p className="muted">Your confirmed retreat tickets will appear here.</p><span className="empty">No tickets yet</span></div><div className="dash-card"><Check/><h3>Payment history</h3><p className="muted">Payments are verified securely by RETUNORI.</p><span className="empty">No payments yet</span></div></div></section> }
function App() { return <Layout><Routes><Route path="/" element={<Home/>}/><Route path="/retreats" element={<Retreats/>}/><Route path="/retreats/:slug" element={<Detail/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<Login register/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/announcements" element={<section className="page section"><div className="eyebrow">STAY IN THE LOOP</div><h1>Announcements</h1><p className="lead">Updates from the RETUNORI community will appear here.</p></section>}/><Route path="/contact" element={<section className="page section"><div className="eyebrow">WE’RE HERE</div><h1>Get in touch.</h1><p className="lead">Have a question about a retreat? Email hello@retunori.com and our team will get back to you.</p></section>}/></Routes></Layout> }
function PortalApp() { return <Layout><Routes><Route path="/" element={<Home/>}/><Route path="/retreats" element={<Retreats/>}/><Route path="/retreats/:slug" element={<Detail/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<Login register/>}/><Route path="/dashboard" element={<AttendeePortal/>}/><Route path="/admin" element={<AdminPortal/>}/><Route path="/staff" element={<StaffPortal/>}/><Route path="/announcements" element={<section className="page section"><div className="eyebrow">STAY IN THE LOOP</div><h1>Announcements</h1><p className="lead">Updates from the RETUNORI community will appear here.</p></section>}/><Route path="/contact" element={<section className="page section"><div className="eyebrow">WEâ€™RE HERE</div><h1>Get in touch.</h1><p className="lead">Have a question about a retreat? Email hello@retunori.com and our team will get back to you.</p></section>}/></Routes></Layout> }
function PortalApp2() { return <Layout><Routes><Route path="/" element={<Home/>}/><Route path="/retreats" element={<Retreats/>}/><Route path="/retreats/:slug" element={<Detail/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<Login register/>}/><Route path="/dashboard" element={<AttendeePortal/>}/><Route path="/admin" element={<AdminPortal/>}/><Route path="/staff" element={<StaffPortal/>}/><Route path="/announcements" element={<Navigate to="/" replace/>}/><Route path="/contact" element={<ContactPage/>}/><Route path="/privacy" element={<LegalPage slug="privacy"/>}/><Route path="/terms" element={<LegalPage slug="terms"/>}/></Routes></Layout> }
function PortalApp3() { return <Layout><Routes><Route path="/" element={<Home/>}/><Route path="/retreats" element={<Retreats/>}/><Route path="/retreats/:slug" element={<Detail/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<Login register/>}/><Route path="/purchase" element={<PurchasePage/>}/><Route path="/dashboard" element={<AttendeePortal/>}/><Route path="/admin" element={<AdminPortal/>}/><Route path="/staff" element={<StaffPortal/>}/><Route path="/announcements" element={<Navigate to="/" replace/>}/><Route path="/contact" element={<ContactPage/>}/><Route path="/privacy" element={<LegalPage slug="privacy"/>}/><Route path="/terms" element={<LegalPage slug="terms"/>}/></Routes></Layout> }
function PortalApp4() { return <Layout><Routes><Route path="/" element={<Home/>}/><Route path="/about" element={<AboutPage/>}/><Route path="/retreats" element={<Retreats/>}/><Route path="/retreats/:slug" element={<RetreatDetail/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<RegistrationPage/>}/><Route path="/reset-password" element={<PasswordReset/>}/><Route path="/purchase" element={<PurchaseFlow/>}/><Route path="/dashboard" element={<AttendeeDashboard/>}/><Route path="/account" element={<AccountPage/>}/><Route path="/admin" element={<AdminDashboard/>}/><Route path="/admin/retreats" element={<AdminRetreats/>}/><Route path="/admin/manage" element={<AdminManage/>}/><Route path="/admin/content" element={<AdminContent/>}/><Route path="/admin/publishing" element={<AdminPublishing/>}/><Route path="/admin/media" element={<AdminMedia/>}/><Route path="/admin/staff" element={<AdminStaff/>}/><Route path="/admin/attendees" element={<AdminAttendees/>}/><Route path="/admin/payments" element={<AdminPayments/>}/><Route path="/admin/tickets" element={<AdminTickets/>}/><Route path="/admin/backups" element={<AdminBackups/>}/><Route path="/admin/course-options" element={<AdminCourseAssignments/>}/><Route path="/admin/notifications" element={<AdminNotifications/>}/><Route path="/staff" element={<StaffDashboard/>}/><Route path="/announcements" element={<Navigate to="/" replace/>}/><Route path="/contact" element={<ContactPage/>}/><Route path="/privacy" element={<LegalPage slug="privacy"/>}/><Route path="/terms" element={<LegalPage slug="terms"/>}/></Routes></Layout> }
function RoleDashboardRedirect() { const location = useLocation(); const navigate = useNavigate(); useEffect(() => { if (location.pathname !== '/dashboard') return; try { const user = JSON.parse(localStorage.getItem('retunori_user') || 'null'); if (user?.role === 'admin') navigate('/admin', { replace: true }); else if (user?.role === 'staff') navigate('/staff', { replace: true }) } catch {} }, [location.pathname, navigate]); return null }
function SeoMetadata() { const location = useLocation(); useEffect(() => { api.get('/seo', { params: { path: location.pathname } }).then(response => { const data = response.data; if (data.page_title) document.title = data.page_title; if (data.meta_description) { let tag = document.querySelector('meta[name="description"]'); if (!tag) { tag = document.createElement('meta'); tag.name = 'description'; document.head.appendChild(tag) } tag.content = data.meta_description } if (data.social_image_url) { let tag = document.querySelector('meta[property="og:image"]'); if (!tag) { tag = document.createElement('meta'); tag.setAttribute('property', 'og:image'); document.head.appendChild(tag) } tag.content = data.social_image_url } }).catch(() => {}) }, [location.pathname]); return null }
function RoutedApp() { const location = useLocation(); return <AppErrorBoundary key={location.pathname}><Suspense fallback={<div className="loading">Loading…</div>}><PortalApp4/></Suspense></AppErrorBoundary> }
createRoot(document.getElementById('root')).render(<BrowserRouter><RoleDashboardRedirect/><SeoMetadata/><RoutedApp/></BrowserRouter>)
