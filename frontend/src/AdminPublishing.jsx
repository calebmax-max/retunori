import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Save, Send, Trash2 } from 'lucide-react'
import './portal.css'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem('retunori_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })

export default function AdminPublishing() {
  const [announcements, setAnnouncements] = useState([]); const [retreats, setRetreats] = useState([]); const [contacts, setContacts] = useState([]); const [expandedContact, setExpandedContact] = useState(null); const [featured, setFeatured] = useState([]); const [files, setFiles] = useState([]); const [form, setForm] = useState({ title: '', body: '', retreat_id: '', expires_at: '', is_pinned: false, is_published: true }); const [status, setStatus] = useState('')
  const load = () => Promise.all([api.get('/admin/announcements'), api.get('/admin/retreats'), api.get('/homepage'), api.get('/admin/contact-submissions')]).then(([a, r, h, c]) => { setAnnouncements(a.data); setRetreats(r.data.filter(item => item.status === 'published')); setFeatured((h.data.featured_retreats || []).map(item => item.id)); setContacts(c.data) }).catch(e => setStatus(e.response?.data?.detail || 'Publishing data could not be loaded'))
  useEffect(() => { load() }, [])
  const publish = async event => {
    event.preventDefault()
    try {
      const payload = { ...form, retreat_id: form.retreat_id ? Number(form.retreat_id) : null, expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null }
      const created = await api.post('/admin/announcements', payload)
      if (files.length) {
        const body = new FormData()
        files.forEach(file => body.append('files', file))
        await api.post(`/admin/announcements/${created.data.id}/images`, body)
      }
      setForm({ title: '', body: '', retreat_id: '', expires_at: '', is_pinned: false, is_published: true })
      setFiles([])
      event.target.reset()
      setStatus('Announcement published.')
      load()
    } catch (e) { setStatus(e.response?.data?.detail || 'Announcement could not be published') }
  }
  const edit = async item => { const title = window.prompt('Announcement title', item.title); if (title === null) return; const body = window.prompt('Announcement body', item.body); if (body === null) return; try { await api.put(`/admin/announcements/${item.id}`, { title, body, is_pinned: item.is_pinned, is_published: item.is_published, retreat_id: item.retreat_id, expires_at: item.expires_at, image_urls: item.image_urls }); setStatus('Announcement updated.'); load() } catch (e) { setStatus(e.response?.data?.detail || 'Announcement could not be updated') } }
  const remove = async id => { if (!window.confirm('Remove this announcement from the public site?')) return; try { await api.delete(`/admin/announcements/${id}`); setStatus('Announcement removed.'); load() } catch (e) { setStatus(e.response?.data?.detail || 'Announcement could not be removed') } }
  const addImages = async (id, selectedFiles) => {
    if (!selectedFiles?.length) return
    const body = new FormData()
    selectedFiles.forEach(file => body.append('files', file))
    try { await api.post(`/admin/announcements/${id}/images`, body); setStatus('Gallery images added.'); load() }
    catch (e) { setStatus(e.response?.data?.detail || 'Images could not be added') }
  }
  const deleteImage = async (item, imageUrl) => {
    if (!window.confirm('Delete this gallery image?')) return
    try { await api.delete(`/admin/announcements/${item.id}/images`, { params: { image_url: imageUrl } }); setStatus('Gallery image deleted.'); load() }
    catch (e) { setStatus(e.response?.data?.detail || 'Image could not be deleted') }
  }
  const saveFeatured = async () => { try { await api.put('/admin/featured-retreats', { retreat_ids: featured }); setStatus('Featured event order saved.') } catch (e) { setStatus(e.response?.data?.detail || 'Featured events could not be saved') } }
  const toggleFeatured = id => setFeatured(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id])
  return <section className="page section manage">
    <div className="eyebrow">ADMINISTRATION</div><h1>Publishing centre.</h1>
    <p className="lead">Manage event stories, homepage experiences and contact submissions.</p>
    {status && <p className="muted form-status">{status}</p>}
    <div className="admin-content-grid">
      <form className="dash-card manage-form" onSubmit={publish}>
        <Send/><h3>Publish event story</h3>
        <input required placeholder="Title" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/>
        <textarea required placeholder="Announcement body" value={form.body} onChange={e=>setForm({...form,body:e.target.value})}/>
        <select value={form.retreat_id} onChange={e=>setForm({...form,retreat_id:e.target.value})}>
          <option value="">Link to an event (optional)</option>
          {retreats.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}
        </select>
        <label>Gallery expiry<input type="datetime-local" value={form.expires_at} onChange={e=>setForm({...form,expires_at:e.target.value})}/></label>
        <small className="muted">Leave empty to keep the story for 32 hours.</small>
        <input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={e=>setFiles(Array.from(e.target.files || []))}/>
        <label className="consent"><input type="checkbox" checked={form.is_pinned} onChange={e=>setForm({...form,is_pinned:e.target.checked})}/> Pin this announcement</label>
        <button className="button primary">Publish <Send size={15}/></button>
      </form>
      <div className="dash-card manage-form"><h3>Featured events</h3><p className="muted">Select published events for the homepage.</p>{retreats.map(item => <label className="consent" key={item.id}><input type="checkbox" checked={featured.includes(item.id)} onChange={()=>toggleFeatured(item.id)}/>{item.title}</label>)}<button className="button primary" type="button" onClick={saveFeatured}><Save size={15}/> Save featured selection</button></div>
    </div>
    <div className="dash-card activity-card">
      <h3>Announcements</h3>
      {announcements.length ? announcements.map(item => <article className="admin-announcement" key={item.id}>
        <div className="report-row">
          <span><strong>{item.title}</strong><small>{item.is_published ? 'Published' : 'Unpublished'} · {item.is_pinned ? 'Pinned' : 'Unpinned'} · {item.image_urls?.length ? `${item.image_urls.length} images · ` : ''}{item.expires_at ? `Expires ${new Date(item.expires_at).toLocaleString()}` : 'No expiry'}</small></span>
          <span className="export-links"><button className="button secondary" type="button" onClick={()=>edit(item)}>Edit</button><button className="button secondary" type="button" onClick={()=>remove(item.id)}><Trash2 size={14}/> Remove</button></span>
        </div>
        {item.image_urls?.length > 0 && <div className="admin-gallery-grid">
          {item.image_urls.map((url, index) => <figure key={url}>
            <img src={url} alt={`${item.title} gallery image ${index + 1}`}/>
            <button className="button secondary" type="button" onClick={() => deleteImage(item, url)}><Trash2 size={14}/> Delete</button>
          </figure>)}
        </div>}
        <label className="admin-add-gallery-images">Add images<input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={event => addImages(item.id, Array.from(event.target.files || []))}/></label>
      </article>) : <p className="muted">No announcements yet.</p>}
    </div>
    <div className="dash-card activity-card"><h3>Contact submissions</h3>{contacts.length ? contacts.map(item => <div className="report-row contact-row" key={item.id}><span><strong>{item.name} · {item.email}</strong><small>{new Date(item.created_at).toLocaleString()} · {item.status}</small>{expandedContact === item.id && <small className="contact-message">{item.message}</small>}</span><button className="button secondary" type="button" onClick={()=>setExpandedContact(expandedContact === item.id ? null : item.id)}>{expandedContact === item.id ? 'Close' : 'Read'}</button></div>) : <p className="muted">No contact submissions yet.</p>}</div>
  </section>
}
