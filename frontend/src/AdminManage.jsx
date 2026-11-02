import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Plus, Save } from 'lucide-react'
import './portal.css'
import { apiErrorMessage } from './apiError'

const slugify = value => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(config => { const token = localStorage.getItem("retunori_token"); if (token) config.headers.Authorization = "Bearer " + token; return config })
export default function AdminManage() {
  const [status, setStatus] = useState(''); const [retreat, setRetreat] = useState({slug:'',title:'',description:'',venue:'',starts_at:'',ends_at:'',price_kes:'',is_free:false,capacity:''}); const [course, setCourse] = useState(''); const [announcement, setAnnouncement] = useState({title:'',body:''})
  const [retreatStatus, setRetreatStatus] = useState(null)
  const [courses, setCourses] = useState([]); const [editingCourse, setEditingCourse] = useState(null)
  const loadCourses = () => api.get('/courses').then(response => setCourses(response.data)).catch(() => setStatus('Course options could not be loaded'))
  useEffect(() => { loadCourses() }, [])
  const action = async (request, message) => { setStatus(''); try { await request(); setStatus(message) } catch (error) { setStatus(apiErrorMessage(error)) } }
  const createCourse = async event => { event.preventDefault(); await action(async () => { await api.post('/admin/courses', {name: course}); setCourse(''); loadCourses() }, 'Course added.') }
  const updateCourse = async event => { event.preventDefault(); await action(async () => { await api.put(`/admin/courses/${editingCourse.id}`, {name: editingCourse.name}); setEditingCourse(null); loadCourses() }, 'Course updated.') }
  const deleteCourse = async item => { if (!window.confirm(`Delete course option "${item.name}"?`)) return; await action(async () => { await api.delete(`/admin/courses/${item.id}`); loadCourses() }, 'Course deleted.') }
  const createRetreat = async event => {
    event.preventDefault()
    setRetreatStatus(null)
    try {
      const response = await api.post('/admin/retreats', {
        ...retreat,
        slug: slugify(retreat.title),
        price_kes: retreat.is_free ? 0 : Number(retreat.price_kes),
        capacity: Number(retreat.capacity),
        starts_at: retreat.starts_at,
        ends_at: retreat.ends_at
      })
      setRetreatStatus({ type: 'success', message: `"${response.data.title}" was saved as ${response.data.status}.` })
      setRetreat({ slug: '', title: '', description: '', venue: '', starts_at: '', ends_at: '', price_kes: '', is_free: false, capacity: '' })
    } catch (error) {
      const message = error.response?.status === 409
        ? 'This event already exists. Change the title or start date, then save it as a new event.'
        : error.response?.status === 403
          ? 'Event not saved. Sign in as an administrator.'
          : apiErrorMessage(error, 'Event not saved. Check the event details and try again.')
      setRetreatStatus({ type: 'error', message })
    }
  }
  return <section className="page section manage"><div className="eyebrow">ADMINISTRATION</div><h1>Manage the retreat calendar.</h1><p className="lead">Changes are written through protected administrator APIs and recorded in activity logs.</p><div className="manage-grid"><form className="dash-card manage-form" onSubmit={createRetreat}><Plus/><h3>Create retreat</h3>{retreatStatus && <div className={`admin-action-status ${retreatStatus.type}`} role="status">{retreatStatus.message}</div>}{[['title','Title'],['venue','Venue'],['starts_at','Start date/time'],['ends_at','End date/time'],...(!retreat.is_free ? [['price_kes','Price in KES']] : []),['capacity','Capacity']].map(([key,label])=><input key={key} required placeholder={label} type={key.includes('at')?'datetime-local':key==='price_kes'||key==='capacity'?'number':'text'} value={retreat[key]} onChange={e=>setRetreat({...retreat,[key]:e.target.value})}/>)}
  <label className="consent"><input type="checkbox" checked={retreat.is_free} onChange={e=>setRetreat({...retreat,is_free:e.target.checked,price_kes:e.target.checked?'0':retreat.price_kes})}/> Free event</label><small className="muted">Free events issue QR tickets immediately without M-Pesa.</small><small className="muted">The public URL is generated automatically from the retreat title.</small><textarea required placeholder="Description" value={retreat.description} onChange={e=>setRetreat({...retreat,description:e.target.value})}/><button className="button primary">Save draft <Save size={15}/></button></form><div className="manage-stack"><div className="dash-card manage-form"><h3>Add course option</h3><form onSubmit={createCourse}><input required placeholder="Course name" value={course} onChange={e=>setCourse(e.target.value)}/><button className="button primary">Add course <Save size={15}/></button></form>{courses.length > 0 && <div className="managed-courses"><span className="managed-courses-label">Course options</span>{courses.map(item => editingCourse?.id === item.id ? <form key={item.id} className="managed-course-row" onSubmit={updateCourse}><input required value={editingCourse.name} onChange={e=>setEditingCourse({...editingCourse,name:e.target.value})}/><button className="button secondary" type="submit">Save</button><button className="button secondary" type="button" onClick={()=>setEditingCourse(null)}>Cancel</button></form> : <div className="managed-course-row" key={item.id}><strong>{item.name}</strong><button className="button secondary" type="button" onClick={()=>setEditingCourse(item)}>Edit</button><button className="button danger" type="button" onClick={()=>deleteCourse(item)}>Delete</button></div>)}</div>}</div><form className="dash-card manage-form" onSubmit={e=>{e.preventDefault();action(()=>api.post('/admin/announcements',announcement),'Announcement published.');setAnnouncement({title:'',body:''})}}><h3>Publish announcement</h3><input required placeholder="Title" value={announcement.title} onChange={e=>setAnnouncement({...announcement,title:e.target.value})}/><textarea required placeholder="Announcement body" value={announcement.body} onChange={e=>setAnnouncement({...announcement,body:e.target.value})}/><button className="button primary">Publish <Save size={15}/></button></form></div></div>{status && <p className="muted form-status">{status}</p>}</section>
}
