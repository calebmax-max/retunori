import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { ArrowRight, CreditCard } from 'lucide-react'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem("retunori_token"); if (token) config.headers.Authorization = "Bearer " + token; return config })

export default function PurchasePage() {
  const [retreats, setRetreats] = useState([]); const [courses, setCourses] = useState([]); const [form, setForm] = useState({ retreat_id:'', course_of_study:'', mpesa_phone:'' }); const [status, setStatus] = useState('')
  useEffect(() => { Promise.all([api.get('/retreats'), api.get('/courses')]).then(([retreatResponse, courseResponse]) => { setRetreats(retreatResponse.data); setCourses(courseResponse.data) }).catch(() => setStatus('Retreats or course options could not be loaded.')) }, [])
  const submit = async event => { event.preventDefault(); setStatus(''); try { const response = await api.post('/registrations', {...form, retreat_id:Number(form.retreat_id)}); setStatus(response.data.message) } catch (e) { if (e.response?.status === 401) setStatus('Please sign in before registering for a retreat.'); else setStatus(e.response?.data?.detail || 'Registration could not be completed.') } }
  return <section className="page section purchase"><div className="eyebrow"><CreditCard size={14}/> RESERVE YOUR PLACE</div><h1>Choose your<br/><em>next experience.</em></h1><p className="lead">Your place is held only after the backend verifies your M-Pesa payment callback.</p><form className="purchase-form" onSubmit={submit}><label>Retreat<select required value={form.retreat_id} onChange={e=>setForm({...form,retreat_id:e.target.value})}><option value="">Select a retreat</option>{retreats.map(r=><option key={r.id} value={r.id}>{r.title} · KES {r.price_kes.toLocaleString()}</option>)}</select></label><label>Course of study<input required placeholder="Your course" value={form.course_of_study} onChange={e=>setForm({...form,course_of_study:e.target.value})}/></label><label>M-Pesa phone number<input required placeholder="07XXXXXXXX" value={form.mpesa_phone} onChange={e=>setForm({...form,mpesa_phone:e.target.value})}/></label><button className="button primary" type="submit">Continue to payment <ArrowRight size={16}/></button>{status && <p className="muted form-status">{status}</p>}</form></section>
}
