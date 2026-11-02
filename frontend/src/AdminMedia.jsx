import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { ImagePlus } from 'lucide-react'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })

export default function AdminMedia() {
  const [retreats, setRetreats] = useState([])
  const [retreatId, setRetreatId] = useState('')
  const [file, setFile] = useState(null)
  const [alt, setAlt] = useState('RETUNORI event image')
  const [status, setStatus] = useState('')
  useEffect(() => { api.get('/admin/retreats').then(response => setRetreats(response.data)).catch(() => setStatus('Events could not be loaded')) }, [])
  const upload = async event => {
    event.preventDefault()
    if (!file || !retreatId) return
    const body = new FormData()
    body.append('file', file)
    body.append('alt_text', alt)
    setStatus('Uploading and converting to WebP…')
    try {
      await api.post(`/admin/retreats/${retreatId}/images`, body)
      setStatus('Image uploaded. It now appears on the event card and event details page.')
      setFile(null)
      event.target.reset()
    } catch (error) {
      setStatus(error.response?.data?.detail || 'Image upload failed')
    }
  }
  return <section className="page section manage"><div className="eyebrow">ADMINISTRATION</div><h1>Event media.</h1><p className="lead">Upload one optimized image for each event. RETUNORI automatically converts it to WebP and uses it on the event card and details page.</p><form className="dash-card manage-form media-form" onSubmit={upload}><ImagePlus/><h3>Upload event image</h3><select required value={retreatId} onChange={e => setRetreatId(e.target.value)}><option value="">Select event</option>{retreats.map(retreat => <option key={retreat.id} value={retreat.id}>{retreat.title}</option>)}</select><input required type="file" accept="image/jpeg,image/png,image/webp" onChange={e => setFile(e.target.files[0])}/><input value={alt} onChange={e => setAlt(e.target.value)} placeholder="Accessible image description"/><button className="button primary">Upload WebP image</button>{status && <p className="muted form-status">{status}</p>}</form></section>
}
