import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { ArrowLeft, ArrowRight, CreditCard } from 'lucide-react'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem("retunori_token"); if (token) config.headers.Authorization = "Bearer " + token; return config })

export default function PurchaseFlow() {
  const navigate = useNavigate(); const [params] = useSearchParams(); const [retreats, setRetreats] = useState([]); const [courses, setCourses] = useState([]); const [form, setForm] = useState({ retreat_id: params.get('retreat') || '', course_of_study: '', mpesa_phone: '' }); const [paymentId, setPaymentId] = useState(null); const [status, setStatus] = useState('')
  const user = (() => {
    try { return JSON.parse(localStorage.getItem('retunori_user') || 'null') } catch { return null }
  })()
  const signOutForAttendee = () => {
    localStorage.removeItem('retunori_token')
    localStorage.removeItem('retunori_user')
    window.dispatchEvent(new Event('retunori-auth-changed'))
    navigate('/login')
  }
  useEffect(() => { Promise.all([api.get('/retreats'), api.get('/courses')]).then(([retreatResponse, courseResponse]) => { setRetreats(retreatResponse.data); setCourses(courseResponse.data) }).catch(() => setStatus('Retreats or course options could not be loaded.')) }, [])
  useEffect(() => { if (!paymentId) return undefined; const startedAt = Date.now(); const timer = window.setInterval(async () => { try { const response = await api.get(`/payments/${paymentId}`); if (response.data.status === 'successful') { window.clearInterval(timer); setStatus('Payment verified. Your ticket is ready.'); window.setTimeout(() => navigate('/dashboard'), 700) } else if (response.data.status === 'failed') { window.clearInterval(timer); setStatus(response.data.error_detail || 'Payment failed. Please try again.') } else if (Date.now() - startedAt >= 10 * 60 * 1000) { window.clearInterval(timer); setStatus('Payment is taking longer than expected. Check your dashboard or try again.') } else setStatus('Payment is still pending. Complete the M-Pesa prompt on your phone.') } catch { window.clearInterval(timer); setStatus('Payment status could not be checked. Please refresh your dashboard.') } }, 10000); return () => window.clearInterval(timer) }, [paymentId, navigate])
  const selectedRetreat = retreats.find(retreat => String(retreat.id) === String(form.retreat_id))
  const submit = async event => {
    event.preventDefault()
    setStatus(selectedRetreat?.is_free ? 'Confirming your free registration…' : 'Requesting M-Pesa payment…')
    try {
      const response = await api.post('/registrations', { ...form, retreat_id: Number(form.retreat_id), mpesa_phone: selectedRetreat?.is_free ? null : form.mpesa_phone })
      if (response.data.provider === 'free') { setStatus(response.data.message); window.setTimeout(() => navigate('/dashboard'), 700) }
      else { setPaymentId(response.data.payment_id); setStatus(response.data.message || 'Complete the M-Pesa prompt on your phone.') }
    } catch (e) {
      if (e.response?.status === 403) setStatus('Registration is available only to attendee accounts. Sign out and sign in with an attendee account.')
      else setStatus(e.response?.data?.detail || 'Registration could not be completed.')
    }
  }
  return <section className="page section purchase"><Link className="back-link" to={selectedRetreat ? `/retreats/${selectedRetreat.slug}` : '/retreats'}><ArrowLeft size={16}/> Back to event</Link><div className="eyebrow"><CreditCard size={14}/> RESERVE YOUR PLACE</div><h1>Choose your<br/><em>next experience.</em></h1><p className="lead">{selectedRetreat?.is_free ? 'Registration is free and your QR ticket is issued immediately.' : 'Your ticket is created only after RETUNORI verifies the Daraja callback.'}</p>{user && user.role !== 'attendee' && <div className="save-status error" role="alert"><strong>Attendee account required</strong><p>You are signed in as {user.role}. Sign out, then sign in with an attendee account before booking.</p><button className="button secondary" type="button" onClick={signOutForAttendee}>Sign out and continue</button>{' '}<Link className="text-link" to="/register">Create attendee account</Link></div>}<form className="purchase-form" onSubmit={submit}><label>Retreat<select required disabled={!!paymentId || (user && user.role !== 'attendee')} value={form.retreat_id} onChange={e=>setForm({...form,retreat_id:e.target.value})}><option value="">Select a retreat</option>{retreats.map(r=><option key={r.id} value={r.id}>{r.title} · {r.is_free ? 'FREE' : `KES ${r.price_kes.toLocaleString()}`} · {r.remaining_capacity} places</option>)}</select></label><label>Course of study<select required disabled={!!paymentId || (user && user.role !== 'attendee')} value={form.course_of_study} onChange={e=>setForm({...form,course_of_study:e.target.value})}><option value="">Select a course</option>{courses.map(course => <option key={course.id} value={course.name}>{course.name}</option>)}</select></label>{!selectedRetreat?.is_free && <label>M-Pesa phone number<input required disabled={!!paymentId || (user && user.role !== 'attendee')} placeholder="07XXXXXXXX" value={form.mpesa_phone} onChange={e=>setForm({...form,mpesa_phone:e.target.value})}/></label>}<button className="button primary" disabled={!!paymentId || (user && user.role !== 'attendee')} type="submit">{selectedRetreat?.is_free ? 'Register for free' : 'Continue to payment'} <ArrowRight size={16}/></button>{status && <p className="muted form-status">{status}</p>}</form></section>
}
