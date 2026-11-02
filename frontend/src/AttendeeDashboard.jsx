import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { CheckCircle2, Download, Save, Ticket } from 'lucide-react'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => {
  const token = localStorage.getItem('retunori_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export function AttendeeDashboard() {
  const [tickets, setTickets] = useState([])
  const [payments, setPayments] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get('/me/tickets'), api.get('/me/payments')])
      .then(([ticketResponse, paymentResponse]) => {
        setTickets(ticketResponse.data)
        setPayments(paymentResponse.data)
      })
      .catch(e => setError(e.response?.data?.detail || 'Your retreat details could not be loaded'))
  }, [])

  const downloadTicket = async ticket => {
    try {
      const response = await api.get(`/me/tickets/${ticket.ticket_number}/pdf`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `${ticket.ticket_number}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('The ticket could not be downloaded. Please try again.')
    }
  }

  return <section className="page section portal">
    <div className="eyebrow">YOUR RETUNORI</div>
    <h1>Your retreat space.</h1>
    {error && <p className="error">{error}</p>}
    {tickets.length > 0 && <div className="latest-ticket-card">
      <div>
        <span className="latest-ticket-label">YOUR TICKET IS READY</span>
        <h2>{tickets[0].retreat_title}</h2>
        <p>{tickets[0].ticket_number} · {tickets[0].course}</p>
      </div>
      <button className="button primary" type="button" onClick={() => downloadTicket(tickets[0])}>
        <Download size={16}/> Download ticket
      </button>
    </div>}
    <div className="portal-grid">
      <div className="dash-card">
        <Ticket/>
        <h3>My tickets</h3>
        {tickets.length ? tickets.map(ticket => <div className="ticket-row" key={ticket.ticket_number}>
          <div><strong>{ticket.retreat_title}</strong><span>{ticket.ticket_number} · {ticket.course}</span></div>
          <button className="icon-link" type="button" onClick={() => downloadTicket(ticket)}><Download size={15}/> PDF</button>
        </div>) : <p className="muted">Verified tickets will appear here after payment confirmation.</p>}
      </div>
      <div className="dash-card">
        <CheckCircle2/>
        <h3>Payment history</h3>
        {payments.length ? payments.map(payment => <div className="report-row" key={payment.transaction_reference}>
          <span><strong>{payment.transaction_reference}</strong><small>{payment.receipt || 'Awaiting M-Pesa receipt'}</small></span>
          <strong>{payment.status} · KES {(payment.paid_amount ?? payment.expected_amount).toLocaleString()}</strong>
        </div>) : <p className="muted">No payment attempts yet.</p>}
      </div>
    </div>
  </section>
}

export function AccountPage() {
  const [form, setForm] = useState({ full_name: '', phone: '', course_of_study: '' })
  const [status, setStatus] = useState('')

  useEffect(() => {
    api.get('/me/profile')
      .then(response => setForm(response.data))
      .catch(() => setStatus('Your account could not be loaded'))
  }, [])

  const submit = async event => {
    event.preventDefault()
    setStatus('')
    try {
      await api.put('/me/profile', form)
      setStatus('Account details updated. Existing tickets retain their historical snapshots.')
    } catch (e) {
      setStatus(e.response?.data?.detail || 'Account details could not be updated')
    }
  }

  return <section className="page section manage">
    <div className="eyebrow">YOUR ACCOUNT</div>
    <h1>Keep your details current.</h1>
    <form className="dash-card manage-form account-form" onSubmit={submit}>
      <input required placeholder="Full name" value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })}/>
      <input required placeholder="Phone number" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })}/>
      <input required placeholder="Course of study" value={form.course_of_study} onChange={e => setForm({ ...form, course_of_study: e.target.value })}/>
      <button className="button primary">Save details <Save size={15}/></button>
      {status && <p className="muted form-status">{status}</p>}
    </form>
  </section>
}
