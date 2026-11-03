import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import sqlite3
from pathlib import Path
import shutil
import secrets
import re
import httpx
from PIL import Image
from io import BytesIO
from sqlalchemy import func, inspect
from sqlalchemy.exc import IntegrityError
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import create_token, current_user, hash_password, require_roles, verify_password
from .core.config import get_settings
from .db import Base, SessionLocal, engine, get_db
from .models import ActivityLog, Announcement, AttendeeProfile, Backup, CheckIn, ContactSubmission, Course, FeaturedRetreat, HomepageContent, LegalPage, Notification, PasswordResetToken, Payment, PaymentCallback, Registration, Retreat, RetreatCourse, RetreatImage, RetreatStatus, Role, ScanAttempt, SeoMetadata, Session, StaffRetreatAssignment, Ticket, User
from .schemas import AnnouncementCreate, AuthResponse, CheckInRequest, ContactCreate, CourseCreate, DarajaCallback, FeaturedUpdate, HomepageUpdate, LegalPageUpdate, LoginRequest, PasswordResetConfirm, PasswordResetRequest, PasswordUpdate, ProfileUpdate, RegisterRequest, RegistrationCreate, RetreatCreate, RetreatOut, RetreatUpdate, SeoUpdate, StaffCreate, UserOut
from .services.tickets import ticket_pdf


# RETUNORI stores event and sales windows as East Africa Time wall-clock values.
EAT_OFFSET = timedelta(hours=3)
def site_now(): return datetime.utcnow() + EAT_OFFSET
from .services.daraja import DarajaNotConfigured, DarajaResponseError, initiate_stk
from .services.reports import report_pdf, report_xlsx
from .services.email import EmailDeliveryError, EmailNotConfigured, send_password_reset_email
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=500)
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


class CachedMediaFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code < 400:
            response.headers["Cache-Control"] = "public, max-age=86400, immutable"
        return response


app.mount("/media", CachedMediaFiles(directory=MEDIA_ROOT), name="media")


def delete_expired_announcements():
    db = SessionLocal()
    try:
        expired = db.scalars(
            select(Announcement).where(
                Announcement.expires_at.is_not(None),
                Announcement.expires_at <= datetime.utcnow(),
            )
        ).all()
        for announcement in expired:
            folder = MEDIA_ROOT / "announcements" / str(announcement.id)
            if folder.is_dir():
                shutil.rmtree(folder)
            db.add(ActivityLog(
                action="announcement.auto_deleted",
                record_type="announcement",
                record_id=str(announcement.id),
                details="Announcement expiry reached",
            ))
            db.delete(announcement)
        if expired:
            db.commit()
        return len(expired)
    finally:
        db.close()


async def _announcement_expiry_loop():
    while True:
        delete_expired_announcements()
        db = SessionLocal()
        try:
            next_expiry = db.scalar(
                select(func.min(Announcement.expires_at)).where(
                    Announcement.expires_at.is_not(None),
                    Announcement.expires_at > datetime.utcnow(),
                )
            )
        finally:
            db.close()
        wake_event = app.state.announcement_expiry_wake
        wake_event.clear()
        if next_expiry is None:
            timeout = 300
        else:
            timeout = max(0.0, (next_expiry - datetime.utcnow()).total_seconds())
        try:
            await asyncio.wait_for(wake_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass


def wake_announcement_expiry_loop():
    wake_event = getattr(app.state, "announcement_expiry_wake", None)
    loop = getattr(app.state, "announcement_expiry_loop", None)
    if wake_event and loop and not loop.is_closed():
        loop.call_soon_threadsafe(wake_event.set)


@app.on_event("startup")
def startup():
    if settings.app_env.lower() == "production" and settings.jwt_secret == "development-only-change-me-please-use-a-long-random-secret":
        raise RuntimeError("JWT_SECRET must be configured in production")
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("announcements")}
            if "retreat_id" not in columns:
                connection.exec_driver_sql("ALTER TABLE announcements ADD COLUMN retreat_id INTEGER REFERENCES retreats(id)")
            if "expires_at" not in columns:
                connection.exec_driver_sql("ALTER TABLE announcements ADD COLUMN expires_at DATETIME")
            if "image_urls" not in columns:
                connection.exec_driver_sql("ALTER TABLE announcements ADD COLUMN image_urls TEXT NOT NULL DEFAULT '[]'")
            retreat_columns = {column["name"] for column in inspect(connection).get_columns("retreats")}
            if "is_free" not in retreat_columns:
                connection.exec_driver_sql("ALTER TABLE retreats ADD COLUMN is_free BOOLEAN NOT NULL DEFAULT 0")
    for image_file in (MEDIA_ROOT / "retreats").rglob("*") if (MEDIA_ROOT / "retreats").exists() else []:
        if image_file.is_file() and image_file.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            webp_file = image_file.with_suffix(".webp")
            try:
                with Image.open(image_file) as source:
                    source.convert("RGB").save(webp_file, "WEBP", quality=82, method=6)
                image_file.unlink()
            except (OSError, ValueError):
                continue

    db = SessionLocal()
    try:
        for retreat_image in db.scalars(select(RetreatImage)).all():
            if retreat_image.url:
                relative_path = retreat_image.url.removeprefix("/media/")
                if not (MEDIA_ROOT / relative_path).is_file():
                    db.delete(retreat_image)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        for retreat_image in db.scalars(select(RetreatImage)).all():
            if retreat_image.url:
                path = Path(retreat_image.url.removeprefix("/media/"))
                if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                    retreat_image.url = f"{path.with_suffix('.webp').as_posix()}"
                    retreat_image.url = "/media/" + retreat_image.url
        db.commit()
        ended = db.scalars(select(Retreat).where(Retreat.ends_at < datetime.utcnow(), Retreat.status != RetreatStatus.archived)).all()
        for retreat in ended:
            retreat.status = RetreatStatus.archived
            retreat.sales_open = False
            db.add(ActivityLog(action="retreat.auto_archived", record_type="retreat", record_id=str(retreat.id), details="Retreat end time passed"))
        if not db.scalar(select(LegalPage).where(LegalPage.slug == "privacy")):
            db.add(LegalPage(slug="privacy", title="Privacy Policy", body="RETUNORI collects the account, contact, registration, payment and attendance information needed to operate retreat registration and check-in. We do not publish attendee lists. Contact RETUNORI to request correction of your records or ask a data-protection question."))
        if not db.scalar(select(LegalPage).where(LegalPage.slug == "terms")):
            db.add(LegalPage(slug="terms", title="Terms of Service", body="RETUNORI provides retreat registration and ticketing. A ticket is issued only after a payment is successfully verified by the backend. Ticket details are personal to the registered attendee and must be presented at check-in. Contact RETUNORI support for corrections or questions."))
        db.commit()
    finally:
        db.close()
    delete_expired_announcements()
    app.state.announcement_expiry_loop = asyncio.get_running_loop()
    app.state.announcement_expiry_wake = asyncio.Event()
    app.state.announcement_expiry_task = asyncio.create_task(_announcement_expiry_loop())
    app.state.automatic_backup_task = asyncio.create_task(_automatic_backup_loop())


@app.on_event("shutdown")
async def shutdown():
    announcement_task = getattr(app.state, "announcement_expiry_task", None)
    if announcement_task:
        announcement_task.cancel()
        try: await announcement_task
        except asyncio.CancelledError: pass
    task = getattr(app.state, "automatic_backup_task", None)
    if task:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass


async def _automatic_backup_loop():
    while True:
        await asyncio.sleep(60 * 60)
        monitor_db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=15)
            delayed = monitor_db.scalars(select(Payment).where(Payment.status == "pending", Payment.requested_at <= cutoff)).all()
            for payment in delayed:
                marker = f"payment {payment.id}"
                already_notified = monitor_db.scalar(select(Notification).where(Notification.kind == "payment.delayed", Notification.body.contains(marker)))
                if not already_notified:
                    monitor_db.add(Notification(kind="payment.delayed", title="Delayed payment", body=f"Pending payment {payment.id} has not received a verified callback yet."))
            monitor_db.commit()
        finally:
            monitor_db.close()
        if not settings.automatic_backups_enabled or engine.url.get_backend_name() != "sqlite": continue
        db = SessionLocal()
        try:
            latest = db.scalar(select(Backup).order_by(Backup.created_at.desc()))
            if latest and latest.created_at > datetime.utcnow() - timedelta(hours=24): continue
            source = Path(engine.url.database or "retunori.db").resolve()
            if not source.exists(): continue
            storage = source.parent / "backups"; storage.mkdir(exist_ok=True)
            filename = f"retunori-auto-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.db"; target = storage / filename
            source_connection = sqlite3.connect(source); target_connection = sqlite3.connect(target)
            try: source_connection.backup(target_connection)
            finally: target_connection.close(); source_connection.close()
            db.add(Backup(filename=filename, storage_path=str(target), created_by=None)); db.commit()
        finally: db.close()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "retunori-api"}


@app.head("/api/health", include_in_schema=False)
def health_head():
    return Response(status_code=200)

@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
@limiter.limit("20/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(payload.password), role=Role.attendee)
    user.attendee_profile = AttendeeProfile(full_name=payload.full_name, phone=payload.phone, course_of_study=payload.course_of_study)
    db.add(user); db.commit(); db.refresh(user)
    token = create_token(user, db); db.add(ActivityLog(user_id=user.id, action="auth.registered", record_type="user", record_id=str(user.id))); db.commit()
    return {"access_token": token, "user": {"id": user.id, "email": user.email, "role": user.role, "full_name": payload.full_name}}

@app.post("/api/auth/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    full_name = user.attendee_profile.full_name if user.attendee_profile else None
    token = create_token(user, db); db.add(ActivityLog(user_id=user.id, action="auth.logged_in", record_type="user", record_id=str(user.id))); db.commit()
    return {"access_token": token, "user": {"id": user.id, "email": user.email, "role": user.role, "full_name": full_name}}


@app.post("/api/auth/logout")
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(Session).filter(Session.user_id == user.id, Session.revoked_at.is_(None)).update({Session.revoked_at: datetime.utcnow()})
    db.add(ActivityLog(user_id=user.id, action="auth.logged_out", record_type="user", record_id=str(user.id))); db.commit()
    return {"status": "logged_out"}


@app.post("/api/auth/password-reset/request")
@limiter.limit("5/minute")
def password_reset_request(request: Request, payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user:
        raw = secrets.token_urlsafe(32); digest = hashlib.sha256(raw.encode()).hexdigest()
        reset_token = PasswordResetToken(user_id=user.id, token_hash=digest, expires_at=datetime.utcnow() + timedelta(minutes=30))
        db.add(reset_token)
        db.flush()
        reset_url = f"{settings.frontend_origin.rstrip('/')}/reset-password?token={raw}"
        try:
            send_password_reset_email(recipient=user.email, reset_url=reset_url)
            db.commit()
        except (EmailNotConfigured, EmailDeliveryError):
            db.rollback()
            # Keep account-existence responses indistinguishable; configure SMTP before production use.
            pass
    return {"message": "If an account exists for that email, reset instructions will be sent."}


@app.post("/api/auth/password-reset/confirm")
@limiter.limit("5/minute")
def password_reset_confirm(request: Request, payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    digest = hashlib.sha256(payload.token.encode()).hexdigest(); item = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == digest, PasswordResetToken.used_at.is_(None)))
    if not item or item.expires_at <= datetime.utcnow(): raise HTTPException(400, "This reset link is invalid or expired")
    user = db.get(User, item.user_id)
    user.password_hash = hash_password(payload.password)
    item.used_at = datetime.utcnow()
    db.query(Session).filter(Session.user_id == user.id, Session.revoked_at.is_(None)).update({Session.revoked_at: datetime.utcnow()})
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).update({PasswordResetToken.used_at: datetime.utcnow()})
    db.commit()
    return {"message": "Password updated. Please sign in again."}

@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role, "full_name": user.attendee_profile.full_name if user.attendee_profile else None}


@app.get("/api/me/profile")
def my_profile(user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    profile = user.attendee_profile
    if not profile: raise HTTPException(404, "Attendee profile not found")
    return {"id": user.id, "email": user.email, "full_name": profile.full_name, "phone": profile.phone, "course_of_study": profile.course_of_study}


@app.put("/api/me/profile")
def update_my_profile(payload: ProfileUpdate, user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    profile = user.attendee_profile
    if not profile: raise HTTPException(404, "Attendee profile not found")
    for key, value in payload.model_dump().items(): setattr(profile, key, value)
    db.add(ActivityLog(user_id=user.id, action="attendee.profile_updated", record_type="attendee_profile", record_id=str(profile.id))); db.commit()
    return {"id": user.id, "email": user.email, **payload.model_dump()}

@app.get("/api/retreats", response_model=list[RetreatOut])
def public_retreats(db: Session = Depends(get_db)):
    _sync_sales_windows(db)
    retreats = db.scalars(select(Retreat).where(Retreat.status == RetreatStatus.published, Retreat.starts_at > site_now()).order_by(Retreat.starts_at)).all()
    return [_public_retreat_data(db, retreat) for retreat in retreats]


def _sync_sales_windows(db: Session):
    now = site_now(); changed = False
    for retreat in db.scalars(select(Retreat).where(Retreat.status.in_([RetreatStatus.published, RetreatStatus.scheduled]))).all():
        should_open = bool(retreat.sales_opens_at and now >= retreat.sales_opens_at and (not retreat.sales_closes_at or now <= retreat.sales_closes_at) and now < retreat.starts_at and retreat.status == RetreatStatus.published)
        should_close = bool(retreat.sales_closes_at and now > retreat.sales_closes_at)
        if should_close and retreat.sales_open:
            retreat.sales_open = False; db.add(ActivityLog(action="retreat.sales_auto_closed", record_type="retreat", record_id=str(retreat.id))); changed = True
        elif should_open and not retreat.sales_open:
            retreat.sales_open = True; db.add(ActivityLog(action="retreat.sales_auto_opened", record_type="retreat", record_id=str(retreat.id))); changed = True
    if changed: db.commit()


def _retreat_slug(title: str, db: Session) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:160] or "retreat"
    slug = base
    suffix = 2
    while db.scalar(select(Retreat).where(Retreat.slug == slug)):
        slug = f"{base[:175-len(str(suffix))-1]}-{suffix}"
        suffix += 1
    return slug


def _public_retreat_data(db: Session, retreat: Retreat) -> dict:
    sold = db.scalar(select(func.count(Ticket.id)).where(Ticket.retreat_id == retreat.id)) or 0
    reserved = db.scalar(select(func.count(Registration.id)).where(Registration.retreat_id == retreat.id, Registration.status.in_(["pending", "paid"]))) or 0
    data = RetreatOut.model_validate(retreat).model_dump()
    data["tickets_sold"] = sold
    data["remaining_capacity"] = max(retreat.capacity - max(sold, reserved), 0)
    assigned = db.scalars(select(Course).join(RetreatCourse, RetreatCourse.course_id == Course.id).where(RetreatCourse.retreat_id == retreat.id, Course.is_active.is_(True)).order_by(Course.name)).all()
    data["course_options"] = assigned or db.scalars(select(Course).where(Course.is_active.is_(True)).order_by(Course.name)).all()
    return data


@app.get("/api/homepage")
def homepage(db: Session = Depends(get_db)):
    content = db.scalar(select(HomepageContent).order_by(HomepageContent.id)).__dict__ if db.scalar(select(HomepageContent).order_by(HomepageContent.id)) else {"headline": "Make room for what matters.", "introduction": "Intentional retreats for meaningful connection.", "support_email": "hello@retunori.com", "support_phone": ""}
    featured = db.scalars(select(Retreat).join(FeaturedRetreat, FeaturedRetreat.retreat_id == Retreat.id).where(Retreat.status == RetreatStatus.published, Retreat.starts_at > site_now()).order_by(FeaturedRetreat.sort_order)).all()
    content.pop("_sa_instance_state", None)
    return {"content": content, "featured_retreats": [_public_retreat_data(db, retreat) for retreat in featured]}

@app.get("/api/retreats/{slug}", response_model=RetreatOut)
def public_retreat(slug: str, db: Session = Depends(get_db)):
    _sync_sales_windows(db)
    retreat = db.scalar(select(Retreat).where(Retreat.slug == slug, Retreat.status == RetreatStatus.published))
    if not retreat: raise HTTPException(404, "Retreat not found")
    if retreat.starts_at <= site_now(): raise HTTPException(404, "Retreat not found")
    return _public_retreat_data(db, retreat)


@app.get("/api/admin/retreats/preview/{slug}", response_model=RetreatOut)
def preview_retreat(slug: str, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    retreat = db.scalar(select(Retreat).where(Retreat.slug == slug))
    if not retreat: raise HTTPException(404, "Retreat not found")
    return _public_retreat_data(db, retreat)


@app.get("/api/seo")
def public_seo(path: str, db: Session = Depends(get_db)):
    item = db.scalar(select(SeoMetadata).where(SeoMetadata.path == path))
    return item or {"path": path, "page_title": "RETUNORI | Retreats · Experiences · Connections", "meta_description": "Intentional retreats for meaningful connection."}


@app.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)):
    published = db.scalars(select(Retreat).where(Retreat.status == RetreatStatus.published)).all()
    urls = ["<url><loc>/</loc></url>", "<url><loc>/retreats</loc></url>", "<url><loc>/announcements</loc></url>", "<url><loc>/contact</loc></url>"] + [f"<url><loc>/retreats/{item.slug}</loc></url>" for item in published]
    return Response("<?xml version=\"1.0\" encoding=\"UTF-8\"?><urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">" + "".join(urls) + "</urlset>", media_type="application/xml")


@app.get("/api/announcements")
def public_announcements(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    items = db.scalars(select(Announcement).where(Announcement.is_published.is_(True), (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)).order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc())).all()
    return [announcement_response(item, db) for item in items]


def announcement_response(item, db=None):
    try:
        images = json.loads(item.image_urls or "[]")
    except json.JSONDecodeError:
        images = []
    retreat = item.retreat_id and db.get(Retreat, item.retreat_id) if db else None
    return {
        "id": item.id, "title": item.title, "body": item.body,
        "is_pinned": item.is_pinned, "is_published": item.is_published,
        "published_at": item.published_at, "expires_at": item.expires_at,
        "retreat_id": item.retreat_id, "retreat_title": retreat.title if retreat else None,
        "image_urls": images
    }


@app.get("/api/legal/{slug}")
def legal_page(slug: str, db: Session = Depends(get_db)):
    page = db.scalar(select(LegalPage).where(LegalPage.slug == slug))
    if not page: raise HTTPException(404, "Legal page not found")
    return page


@app.post("/api/contact", status_code=201)
@limiter.limit("10/minute")
def contact(request: Request, payload: ContactCreate, db: Session = Depends(get_db)):
    item = ContactSubmission(**payload.model_dump()); db.add(item); db.add(Notification(kind="contact", title="New contact submission", body=f"From {payload.name} ({payload.email}):\n\n{payload.message}")); db.commit()
    return {"status": "received", "message": "Thanks. RETUNORI support will review your message."}


@app.post("/api/admin/announcements", status_code=201)
def create_announcement(payload: AnnouncementCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    values = payload.model_dump()
    values["expires_at"] = values["expires_at"] or datetime.utcnow() + timedelta(hours=32)
    values["image_urls"] = json.dumps(values.pop("image_urls"))
    item = Announcement(**values)
    if item.retreat_id and not db.get(Retreat, item.retreat_id):
        raise HTTPException(404, "Retreat not found")
    db.add(item)
    db.add(ActivityLog(user_id=user.id, action="announcement.created", record_type="announcement"))
    db.commit()
    db.refresh(item)
    wake_announcement_expiry_loop()
    return announcement_response(item, db)


@app.get("/api/admin/announcements")
def admin_announcements(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    items = db.scalars(select(Announcement).order_by(Announcement.published_at.desc())).all()
    return [announcement_response(item, db) for item in items]


@app.put("/api/admin/announcements/{announcement_id}")
def update_announcement(announcement_id: int, payload: AnnouncementCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Announcement, announcement_id)
    if not item: raise HTTPException(404, "Announcement not found")
    values = payload.model_dump()
    values["image_urls"] = json.dumps(values.pop("image_urls"))
    if announcement_id and payload.retreat_id and not db.get(Retreat, payload.retreat_id):
        raise HTTPException(404, "Retreat not found")
    for key, value in values.items(): setattr(item, key, value)
    db.add(ActivityLog(user_id=user.id, action="announcement.updated", record_type="announcement", record_id=str(item.id))); db.commit(); db.refresh(item)
    wake_announcement_expiry_loop()
    return announcement_response(item, db)


@app.delete("/api/admin/announcements/{announcement_id}", status_code=204)
def delete_announcement(announcement_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Announcement, announcement_id)
    if not item: raise HTTPException(404, "Announcement not found")
    db.add(ActivityLog(user_id=user.id, action="announcement.deleted", record_type="announcement", record_id=str(item.id))); db.delete(item); db.commit()


@app.post("/api/admin/announcements/{announcement_id}/images")
async def upload_announcement_images(announcement_id: int, files: list[UploadFile] = File(...), user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Announcement, announcement_id)
    if not item: raise HTTPException(404, "Announcement not found")
    try: urls = json.loads(item.image_urls or "[]")
    except json.JSONDecodeError: urls = []
    folder = MEDIA_ROOT / "announcements" / str(announcement_id)
    folder.mkdir(parents=True, exist_ok=True)
    for file in files:
        if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
        content = await file.read()
        if len(content) > 5 * 1024 * 1024: raise HTTPException(413, "Images must be 5 MB or smaller")
        try:
            with Image.open(BytesIO(content)) as image_file:
                image_file.load()
                image_file = image_file.convert("RGB")
                image_file.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                target = folder / f"{secrets.token_hex(16)}.webp"
                image_file.save(target, "WEBP", quality=82, method=6)
        except (OSError, ValueError):
            raise HTTPException(415, "Images must contain valid JPEG, PNG or WebP data")
        urls.append(f"/media/announcements/{announcement_id}/{target.name}")
    item.image_urls = json.dumps(urls)
    db.commit()
    db.refresh(item)
    return announcement_response(item, db)


@app.delete("/api/admin/announcements/{announcement_id}/images", status_code=200)
def delete_announcement_image(announcement_id: int, image_url: str = Query(...), user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Announcement, announcement_id)
    if not item: raise HTTPException(404, "Announcement not found")
    try: urls = json.loads(item.image_urls or "[]")
    except json.JSONDecodeError: urls = []
    if image_url not in urls: raise HTTPException(404, "Image not found in announcement gallery")
    urls.remove(image_url)
    item.image_urls = json.dumps(urls)
    db.add(ActivityLog(user_id=user.id, action="announcement.image_deleted", record_type="announcement", record_id=str(item.id), details=image_url))
    db.commit()
    path = MEDIA_ROOT / image_url.removeprefix("/media/")
    if path.is_file(): path.unlink()
    db.refresh(item)
    return announcement_response(item, db)


@app.get("/api/admin/contact-submissions")
def contact_submissions(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return db.scalars(select(ContactSubmission).order_by(ContactSubmission.created_at.desc())).all()


@app.put("/api/admin/legal/{slug}")
def update_legal(slug: str, payload: LegalPageUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    if slug not in {"privacy", "terms"}: raise HTTPException(400, "Unsupported legal page")
    page = db.scalar(select(LegalPage).where(LegalPage.slug == slug))
    if not page: page = LegalPage(slug=slug, title=payload.title, body=payload.body); db.add(page)
    else: page.title = payload.title; page.body = payload.body
    db.add(ActivityLog(user_id=user.id, action="legal.updated", record_type="legal_page", record_id=slug)); db.commit(); db.refresh(page)
    return page


@app.put("/api/admin/homepage")
def update_homepage(payload: HomepageUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    content = db.scalar(select(HomepageContent).order_by(HomepageContent.id))
    if not content: content = HomepageContent(**payload.model_dump()); db.add(content)
    else:
        for key, value in payload.model_dump().items(): setattr(content, key, value)
    db.add(ActivityLog(user_id=user.id, action="homepage.updated", record_type="homepage_content")); db.commit(); db.refresh(content)
    return content


@app.put("/api/admin/featured-retreats")
def update_featured(payload: FeaturedUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    retreats = db.scalars(select(Retreat).where(Retreat.id.in_(payload.retreat_ids), Retreat.status == RetreatStatus.published)).all()
    if len(retreats) != len(set(payload.retreat_ids)): raise HTTPException(400, "Featured retreats must be published and valid")
    db.query(FeaturedRetreat).delete()
    for order, retreat_id in enumerate(payload.retreat_ids): db.add(FeaturedRetreat(retreat_id=retreat_id, sort_order=order))
    db.add(ActivityLog(user_id=user.id, action="featured_retreats.updated", record_type="homepage")); db.commit()
    return {"retreat_ids": payload.retreat_ids}


@app.put("/api/admin/seo")
def update_seo(path: str, payload: SeoUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.scalar(select(SeoMetadata).where(SeoMetadata.path == path))
    if not item: item = SeoMetadata(path=path, **payload.model_dump()); db.add(item)
    else:
        for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.add(ActivityLog(user_id=user.id, action="seo.updated", record_type="seo_metadata", details=path)); db.commit(); db.refresh(item)
    return item

@app.get("/api/admin/overview")
def admin_overview(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    sold = db.scalar(select(func.count(Ticket.id))) or 0
    capacity = db.scalar(select(func.coalesce(func.sum(Retreat.capacity), 0))) or 0
    return {"role": user.role, "retreats": db.scalar(select(func.count(Retreat.id))), "registrations": db.scalar(select(func.count(Registration.id))), "paid_attendees": db.scalar(select(func.count(Payment.id)).where(Payment.status == "successful")), "successful_payments": db.scalar(select(func.count(Payment.id)).where(Payment.status == "successful")), "pending_payments": db.scalar(select(func.count(Payment.id)).where(Payment.status == "pending")), "failed_payments": db.scalar(select(func.count(Payment.id)).where(Payment.status == "failed")), "revenue_kes": db.scalar(select(func.coalesce(func.sum(Payment.paid_amount), 0)).where(Payment.status == "successful")), "tickets_sold": sold, "remaining_capacity": max(capacity - sold, 0), "attendance": db.scalar(select(func.count(CheckIn.id))), "message": "Admin overview"}


@app.post("/api/admin/retreats", response_model=RetreatOut, status_code=201)
def create_retreat(payload: RetreatCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(422, "End date and time must be after the start date and time")
    if payload.sales_opens_at and payload.sales_closes_at and payload.sales_closes_at <= payload.sales_opens_at:
        raise HTTPException(422, "Sales closing time must be after opening time")
    if payload.is_free and payload.price_kes != 0: raise HTTPException(422, "Free events must have a price of KES 0")
    if not payload.is_free and payload.price_kes <= 0: raise HTTPException(422, "Paid events must have a price greater than KES 0")
    values = payload.model_dump()
    values["slug"] = values.get("slug") or _retreat_slug(payload.title, db)
    retreat = Retreat(**values)
    db.add(retreat)
    try:
        db.flush()
        db.add(ActivityLog(user_id=user.id, action="retreat.created", record_type="retreat", record_id=str(retreat.id)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A retreat with this slug or title and start date already exists")
    db.refresh(retreat)
    return retreat


@app.get("/api/admin/retreats", response_model=list[RetreatOut])
def admin_retreats(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return db.scalars(select(Retreat).order_by(Retreat.starts_at.desc())).all()


@app.put("/api/admin/retreats/{retreat_id}", response_model=RetreatOut)
def update_retreat(retreat_id: int, payload: RetreatUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    retreat = db.get(Retreat, retreat_id)
    if not retreat: raise HTTPException(404, "Retreat not found")
    changes = payload.model_dump(exclude_unset=True)
    reason = changes.pop("reason", None)
    start = changes.get("starts_at", retreat.starts_at)
    end = changes.get("ends_at", retreat.ends_at)
    if end <= start:
        raise HTTPException(422, "End date and time must be after the start date and time")
    if changes.get("sales_opens_at") and changes.get("sales_closes_at") and changes["sales_closes_at"] <= changes["sales_opens_at"]:
        raise HTTPException(422, "Sales closing time must be after opening time")
    sales_open = changes.get("sales_open", retreat.sales_open)
    sales_closes_at = changes.get("sales_closes_at", retreat.sales_closes_at)
    is_free = changes.get("is_free", retreat.is_free)
    price_kes = changes.get("price_kes", retreat.price_kes)
    if is_free and price_kes != 0: raise HTTPException(422, "Free events must have a price of KES 0")
    if not is_free and price_kes <= 0: raise HTTPException(422, "Paid events must have a price greater than KES 0")
    if sales_open and sales_closes_at and sales_closes_at <= site_now():
        raise HTTPException(422, "Registration is open, so the closing date and time must be in the future. Set a new closing date to reopen registration.")
    for key, value in changes.items(): setattr(retreat, key, value)
    action = "retreat.sales_reopened" if changes.get("sales_open") is True else "retreat.sales_closed" if changes.get("sales_open") is False else "retreat.updated"
    db.add(ActivityLog(user_id=user.id, action=action, record_type="retreat", record_id=str(retreat_id), details=reason or ""))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A retreat with this title and start date already exists")
    db.refresh(retreat)
    return retreat


@app.post("/api/admin/retreats/{retreat_id}/images", status_code=201)
async def upload_retreat_image(retreat_id: int, file: UploadFile = File(...), alt_text: str = "RETUNORI retreat image", user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    retreat = db.get(Retreat, retreat_id)
    if not retreat: raise HTTPException(404, "Retreat not found")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024: raise HTTPException(413, "Images must be 5 MB or smaller")
    folder = MEDIA_ROOT / "retreats" / str(retreat_id); folder.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(BytesIO(content)) as uploaded_image:
            uploaded_image.load()
            uploaded_image = uploaded_image.convert("RGB")
            uploaded_image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            filename = f"{secrets.token_hex(16)}.webp"
            target = folder / filename
            uploaded_image.save(target, "WEBP", quality=82, method=6)
    except (OSError, ValueError):
        raise HTTPException(415, "Images must contain valid JPEG, PNG or WebP data")
    image = RetreatImage(retreat_id=retreat_id, url=f"/media/retreats/{retreat_id}/{filename}", alt_text=alt_text[:180], sort_order=len(retreat.images))
    db.add(image); db.add(ActivityLog(user_id=user.id, action="retreat.image_uploaded", record_type="retreat", record_id=str(retreat_id), details=image.url)); db.commit(); db.refresh(image)
    return image


@app.delete("/api/admin/retreats/{retreat_id}/images/{image_id}", status_code=204)
def delete_retreat_image(retreat_id: int, image_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    image = db.scalar(select(RetreatImage).where(RetreatImage.id == image_id, RetreatImage.retreat_id == retreat_id))
    if not image: raise HTTPException(404, "Retreat image not found")
    path = MEDIA_ROOT / image.url.removeprefix("/media/")
    db.add(ActivityLog(user_id=user.id, action="retreat.image_deleted", record_type="retreat_image", record_id=str(image_id), details=image.url)); db.delete(image); db.commit()
    if path.is_file(): path.unlink()


@app.post("/api/admin/retreats/{retreat_id}/duplicate", response_model=RetreatOut, status_code=201)
def duplicate_retreat(retreat_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    source = db.get(Retreat, retreat_id)
    if not source: raise HTTPException(404, "Retreat not found")
    copy = Retreat(slug=f"{source.slug}-copy-{secrets.token_hex(3)}", title=f"{source.title} Copy", description=source.description, venue=source.venue, location_url=source.location_url, starts_at=source.starts_at, ends_at=source.ends_at, price_kes=source.price_kes, is_free=source.is_free, capacity=source.capacity, status=RetreatStatus.draft, sales_open=False, sales_opens_at=source.sales_opens_at, sales_closes_at=source.sales_closes_at, poster_url=source.poster_url)
    db.add(copy); db.flush()
    for image in source.images:
        source_path = MEDIA_ROOT / image.url.removeprefix("/media/")
        copied_url = image.url
        if source_path.is_file():
            target_folder = MEDIA_ROOT / "retreats" / str(copy.id); target_folder.mkdir(parents=True, exist_ok=True)
            extension = source_path.suffix or ".bin"; target_name = f"{secrets.token_hex(16)}{extension}"; target_path = target_folder / target_name
            shutil.copyfile(source_path, target_path); copied_url = f"/media/retreats/{copy.id}/{target_name}"
        db.add(RetreatImage(retreat_id=copy.id, url=copied_url, alt_text=image.alt_text, sort_order=image.sort_order))
    for link in source.course_links:
        db.add(RetreatCourse(retreat_id=copy.id, course_id=link.course_id))
    db.add(ActivityLog(user_id=user.id, action="retreat.duplicated", record_type="retreat", record_id=str(retreat_id), details=f"created={copy.id}")); db.commit(); db.refresh(copy)
    return copy


@app.post("/api/admin/retreats/{retreat_id}/archive", response_model=RetreatOut)
def archive_retreat(retreat_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    retreat = db.get(Retreat, retreat_id)
    if not retreat: raise HTTPException(404, "Retreat not found")
    retreat.status = RetreatStatus.archived; retreat.sales_open = False; db.add(ActivityLog(user_id=user.id, action="retreat.archived", record_type="retreat", record_id=str(retreat_id))); db.commit(); db.refresh(retreat)
    return retreat


@app.post("/api/admin/staff", response_model=UserOut, status_code=201)
def create_staff(payload: StaffCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, "An account with this email already exists")
    staff = User(email=email, password_hash=hash_password(payload.password), role=Role.staff)
    db.add(staff); db.add(ActivityLog(user_id=user.id, action="staff.created", record_type="user", details=email)); db.commit(); db.refresh(staff)
    return staff


@app.patch("/api/admin/staff/{staff_id}/status")
def update_staff_status(staff_id: int, active: bool, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    staff = db.get(User, staff_id)
    if not staff or staff.role != Role.staff: raise HTTPException(404, "Staff account not found")
    staff.is_active = active; db.add(ActivityLog(user_id=user.id, action="staff.status_updated", record_type="user", record_id=str(staff_id), details=str(active))); db.commit()
    return {"id": staff.id, "is_active": staff.is_active}


@app.patch("/api/admin/staff/{staff_id}/password")
def reset_staff_password(staff_id: int, payload: PasswordUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    staff = db.get(User, staff_id)
    if not staff or staff.role != Role.staff: raise HTTPException(404, "Staff account not found")
    staff.password_hash = hash_password(payload.password)
    db.query(Session).filter(Session.user_id == staff.id, Session.revoked_at.is_(None)).update({Session.revoked_at: datetime.utcnow()})
    db.add(ActivityLog(user_id=user.id, action="staff.password_reset", record_type="user", record_id=str(staff_id))); db.commit()
    return {"status": "password_updated"}


@app.delete("/api/admin/staff/{staff_id}", status_code=204)
def delete_staff(staff_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    staff = db.get(User, staff_id)
    if not staff or staff.role != Role.staff: raise HTTPException(404, "Staff account not found")
    if db.scalar(select(CheckIn).where(CheckIn.staff_id == staff_id)):
        raise HTTPException(409, "Staff with historical check-ins cannot be deleted; suspend the account instead")
    db.query(StaffRetreatAssignment).filter(StaffRetreatAssignment.staff_id == staff_id).delete()
    db.add(ActivityLog(user_id=user.id, action="staff.deleted", record_type="user", record_id=str(staff_id), details=staff.email)); db.delete(staff); db.commit()


@app.get("/api/admin/reports")
def reports(start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    def between(column):
        clauses = []
        if start: clauses.append(column >= start)
        if end: clauses.append(column <= end)
        return clauses
    registration_query = select(func.count(Registration.id)).where(*between(Registration.created_at))
    successful_query = select(func.count(Payment.id)).where(Payment.status == "successful", *between(Payment.requested_at))
    pending_query = select(func.count(Payment.id)).where(Payment.status == "pending", *between(Payment.requested_at))
    failed_query = select(func.count(Payment.id)).where(Payment.status == "failed", *between(Payment.requested_at))
    revenue_query = select(func.coalesce(func.sum(Payment.paid_amount), 0)).where(Payment.status == "successful", *between(Payment.requested_at))
    attendance_query = select(func.count(CheckIn.id)).where(*between(CheckIn.checked_in_at))
    rows = db.execute(select(Retreat.id, Retreat.title, Retreat.capacity, func.count(Ticket.id).label("tickets_sold")).join(Ticket, Ticket.retreat_id == Retreat.id, isouter=True).where(*between(Retreat.starts_at)).group_by(Retreat.id)).all()
    paid_ticket_filter = [Payment.status == "successful", *between(Ticket.created_at)]
    course_rows = db.execute(select(Ticket.course_snapshot, func.count(Ticket.id)).join(Payment, Payment.registration_id == Ticket.registration_id).where(*paid_ticket_filter).group_by(Ticket.course_snapshot)).all()
    repeated_scans = db.scalar(select(func.count(ScanAttempt.id)).where(ScanAttempt.result == "already_checked_in", *between(ScanAttempt.attempted_at))) or 0
    paid_tickets = db.scalar(select(func.count(Ticket.id)).join(Payment, Payment.registration_id == Ticket.registration_id).where(*paid_ticket_filter)) or 0
    attendance = db.scalar(attendance_query) or 0
    return {"filters": {"start": start, "end": end}, "summary": {"registrations": db.scalar(registration_query), "successful_payments": db.scalar(successful_query), "pending_payments": db.scalar(pending_query), "failed_payments": db.scalar(failed_query), "revenue_kes": db.scalar(revenue_query), "attendance": attendance, "paid_tickets": paid_tickets, "no_shows": max(paid_tickets - attendance, 0), "repeated_scan_attempts": repeated_scans}, "by_course": [{"course": course, "attendees": count} for course, count in course_rows], "retreats": [{"id": r.id, "title": r.title, "capacity": r.capacity, "tickets_sold": r.tickets_sold, "remaining": max(r.capacity - r.tickets_sold, 0)} for r in rows]}


def _report_rows(db: Session) -> list[dict]:
    return [{"retreat": r.title, "capacity": r.capacity, "tickets_sold": sold, "remaining": max(r.capacity - sold, 0)} for r, sold in db.execute(select(Retreat, func.count(Ticket.id)).join(Ticket, Ticket.retreat_id == Retreat.id, isouter=True).group_by(Retreat.id)).all()]


@app.get("/api/admin/reports/export.xlsx")
def export_xlsx(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return StreamingResponse(report_xlsx(_report_rows(db)), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=retunori-report.xlsx"})


@app.get("/api/admin/reports/export.pdf")
def export_pdf(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return StreamingResponse(report_pdf("RETUNORI Retreat Report", _report_rows(db)), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=retunori-report.pdf"})


@app.get("/api/admin/notifications")
def admin_notifications(kind: str = "", unread_only: bool = False, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    query = select(Notification).order_by(Notification.created_at.desc())
    if kind.strip(): query = query.where(Notification.kind == kind.strip())
    if unread_only: query = query.where(Notification.is_read.is_(False))
    return db.scalars(query).all()


@app.get("/api/admin/activity-logs")
def activity_logs(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return db.scalars(select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(250)).all()


@app.post("/api/admin/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if not item: raise HTTPException(404, "Notification not found")
    item.is_read = True; db.commit(); return {"status": "read"}


@app.post("/api/admin/notifications/read-all")
def mark_all_notifications_read(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.is_read.is_(False)).update({Notification.is_read: True}); db.commit(); return {"status": "read_all"}


@app.post("/api/admin/notifications/{notification_id}/archive")
def archive_notification(notification_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if not item: raise HTTPException(404, "Notification not found")
    item.is_archived = True; db.commit(); return {"status": "archived"}


@app.delete("/api/admin/notifications/{notification_id}", status_code=204)
def delete_notification(notification_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if not item: raise HTTPException(404, "Notification not found")
    db.delete(item); db.commit()


@app.get("/api/admin/backups")
def backups(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return [{"id": b.id, "filename": b.filename, "created_at": b.created_at, "status": b.status} for b in db.scalars(select(Backup).order_by(Backup.created_at.desc())).all()]


@app.post("/api/admin/backups", status_code=201)
def create_backup(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    if engine.url.get_backend_name() != "sqlite": raise HTTPException(501, "PostgreSQL backups require a configured pg_dump storage command")
    source = Path(engine.url.database or "retunori.db").resolve(); storage = source.parent / "backups"; storage.mkdir(exist_ok=True); filename = f"retunori-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.db"; target = storage / filename
    if not source.exists(): raise HTTPException(404, "Database file not found")
    shutil.copy2(source, target); item = Backup(filename=filename, storage_path=str(target), created_by=user.id); db.add(item); db.add(ActivityLog(user_id=user.id, action="backup.created", record_type="backup", details=filename)); db.commit(); db.refresh(item)
    return {"id": item.id, "filename": item.filename, "created_at": item.created_at, "status": item.status}


@app.get("/api/admin/backups/{backup_id}/download")
def download_backup(backup_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    item = db.get(Backup, backup_id)
    if not item or not Path(item.storage_path).is_file(): raise HTTPException(404, "Backup not found")
    return StreamingResponse(open(item.storage_path, "rb"), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{item.filename}"'})


@app.post("/api/admin/backups/{backup_id}/restore")
def restore_backup(backup_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    if engine.url.get_backend_name() != "sqlite": raise HTTPException(501, "PostgreSQL restore must be performed through the configured database backup provider")
    item = db.get(Backup, backup_id)
    source = Path(item.storage_path) if item else None
    target = Path(engine.url.database or "retunori.db").resolve()
    if not source or not source.is_file(): raise HTTPException(404, "Backup not found")
    safety = target.with_name(f"{target.stem}-pre-restore-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}{target.suffix}")
    shutil.copy2(target, safety) if target.is_file() else None
    shutil.copy2(source, target)
    db.add(ActivityLog(user_id=user.id, action="backup.restored", record_type="backup", record_id=str(backup_id), details=f"Safety copy: {safety.name}")); db.commit()
    return {"status": "restored", "restart_required": True, "safety_copy": safety.name}


@app.post("/api/admin/assignments")
def assign_staff(staff_id: int, retreat_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    staff = db.get(User, staff_id); retreat = db.get(Retreat, retreat_id)
    if not staff or staff.role != Role.staff or not retreat: raise HTTPException(400, "Staff member or retreat not found")
    if db.scalar(select(StaffRetreatAssignment).where(StaffRetreatAssignment.staff_id == staff_id, StaffRetreatAssignment.retreat_id == retreat_id)): return {"status": "already_assigned"}
    db.add(StaffRetreatAssignment(staff_id=staff_id, retreat_id=retreat_id)); db.add(ActivityLog(user_id=user.id, action="staff.assigned", record_type="retreat", record_id=str(retreat_id))); db.commit()
    return {"status": "assigned"}


@app.get("/api/admin/staff")
def staff_accounts(user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    return [{"id": item.id, "email": item.email, "is_active": item.is_active} for item in db.scalars(select(User).where(User.role == Role.staff).order_by(User.email)).all()]


@app.get("/api/admin/attendees")
def admin_attendees(name: str = "", user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    query = select(User).join(AttendeeProfile).where(User.role == Role.attendee)
    if name.strip(): query = query.where(AttendeeProfile.full_name.ilike(f"%{name.strip()}%"))
    attendees = db.scalars(query.order_by(AttendeeProfile.full_name).limit(100)).all()
    result = []
    for attendee in attendees:
        payments = db.scalars(select(Payment).where(Payment.attendee_id == attendee.id).order_by(Payment.requested_at.desc())).all()
        tickets = db.scalars(select(Ticket).where(Ticket.attendee_id == attendee.id).order_by(Ticket.created_at.desc())).all()
        result.append({"id": attendee.id, "email": attendee.email, "full_name": attendee.attendee_profile.full_name, "phone": attendee.attendee_profile.phone, "course_of_study": attendee.attendee_profile.course_of_study, "payments": [{"status": item.status, "expected_amount": item.expected_amount, "paid_amount": item.paid_amount, "receipt": item.mpesa_receipt, "requested_at": item.requested_at} for item in payments], "tickets": [{"ticket_number": item.ticket_number, "retreat_title": item.retreat_title_snapshot, "course": item.course_snapshot, "created_at": item.created_at} for item in tickets]})
    return result


@app.get("/api/admin/payments")
def admin_payments(status: str = "", user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    query = select(Payment).order_by(Payment.requested_at.desc()).limit(500)
    if status in {"pending", "successful", "failed"}: query = query.where(Payment.status == status)
    result = []
    for payment in db.scalars(query).all():
        profile = db.scalar(select(AttendeeProfile).where(AttendeeProfile.user_id == payment.attendee_id))
        retreat = db.get(Retreat, payment.retreat_id)
        result.append({"id": payment.id, "attendee_name": profile.full_name if profile else "Unknown", "retreat_title": retreat.title if retreat else "Archived retreat", "expected_amount": payment.expected_amount, "paid_amount": payment.paid_amount, "phone_number": payment.phone_number, "transaction_reference": payment.transaction_reference, "receipt": payment.mpesa_receipt, "status": payment.status, "requested_at": payment.requested_at, "callback_at": payment.callback_at, "error_detail": payment.error_detail})
    return result


@app.get("/api/admin/tickets")
def admin_tickets(retreat_id: int | None = Query(default=None), user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    query = select(Ticket).order_by(Ticket.created_at.desc()).limit(500)
    if retreat_id is not None: query = query.where(Ticket.retreat_id == retreat_id)
    result = []
    for ticket in db.scalars(query).all():
        checkin = db.scalar(select(CheckIn).where(CheckIn.ticket_id == ticket.id))
        payment = db.scalar(select(Payment).where(Payment.registration_id == ticket.registration_id))
        result.append({"ticket_number": ticket.ticket_number, "attendee_name": ticket.attendee_name_snapshot, "course": ticket.course_snapshot, "retreat_title": ticket.retreat_title_snapshot, "price_kes": ticket.price_snapshot, "payment_status": payment.status if payment else "unknown", "receipt": payment.mpesa_receipt if payment else None, "checked_in_at": checkin.checked_in_at if checkin else None, "created_at": ticket.created_at})
    return result


@app.put("/api/admin/attendees/{attendee_id}")
def correct_attendee(attendee_id: int, payload: ProfileUpdate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    attendee = db.get(User, attendee_id)
    if not attendee or attendee.role != Role.attendee or not attendee.attendee_profile: raise HTTPException(404, "Attendee not found")
    before = {"full_name": attendee.attendee_profile.full_name, "phone": attendee.attendee_profile.phone, "course_of_study": attendee.attendee_profile.course_of_study}
    for key, value in payload.model_dump().items(): setattr(attendee.attendee_profile, key, value)
    db.add(ActivityLog(user_id=user.id, action="attendee.details_corrected", record_type="attendee_profile", record_id=str(attendee.attendee_profile.id), details=json.dumps({"before": before, "after": payload.model_dump()}))); db.commit()
    return {"id": attendee.id, "email": attendee.email, **payload.model_dump()}


@app.get("/api/staff/assignments")
def staff_assignments(user: User = Depends(require_roles(Role.staff, Role.admin)), db: Session = Depends(get_db)):
    if user.role == Role.admin: return db.scalars(select(Retreat).where(Retreat.status != RetreatStatus.archived).order_by(Retreat.starts_at)).all()
    return db.scalars(select(Retreat).join(StaffRetreatAssignment, StaffRetreatAssignment.retreat_id == Retreat.id).where(StaffRetreatAssignment.staff_id == user.id, Retreat.status != RetreatStatus.archived).order_by(Retreat.starts_at)).all()


@app.get("/api/courses")
def courses(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name} for c in db.scalars(select(Course).where(Course.is_active.is_(True)).order_by(Course.name)).all()]


@app.post("/api/admin/courses", status_code=201)
def create_course(payload: CourseCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    if db.scalar(select(Course).where(Course.name == payload.name)): raise HTTPException(409, "Course already exists")
    course = Course(name=payload.name); db.add(course); db.add(ActivityLog(user_id=user.id, action="course.created", record_type="course", details=payload.name)); db.commit(); db.refresh(course)
    return {"id": course.id, "name": course.name}


@app.put("/api/admin/courses/{course_id}")
def update_course(course_id: int, payload: CourseCreate, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if not course: raise HTTPException(404, "Course not found")
    duplicate = db.scalar(select(Course).where(Course.name == payload.name, Course.id != course_id))
    if duplicate: raise HTTPException(409, "Course already exists")
    course.name = payload.name
    db.add(ActivityLog(user_id=user.id, action="course.updated", record_type="course", details=payload.name))
    db.commit()
    db.refresh(course)
    return {"id": course.id, "name": course.name}


@app.delete("/api/admin/courses/{course_id}", status_code=204)
def delete_course(course_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if not course: raise HTTPException(404, "Course not found")
    db.delete(course)
    db.add(ActivityLog(user_id=user.id, action="course.deleted", record_type="course", details=course.name))
    db.commit()


@app.post("/api/admin/retreats/{retreat_id}/courses/{course_id}")
def assign_retreat_course(retreat_id: int, course_id: int, user: User = Depends(require_roles(Role.admin)), db: Session = Depends(get_db)):
    retreat = db.get(Retreat, retreat_id); course = db.get(Course, course_id)
    if not retreat or not course: raise HTTPException(404, "Retreat or course not found")
    if not db.scalar(select(RetreatCourse).where(RetreatCourse.retreat_id == retreat_id, RetreatCourse.course_id == course_id)):
        db.add(RetreatCourse(retreat_id=retreat_id, course_id=course_id)); db.add(ActivityLog(user_id=user.id, action="retreat.course_assigned", record_type="retreat_course", details=f"{retreat_id}:{course_id}")); db.commit()
    return {"status": "assigned", "retreat_id": retreat_id, "course_id": course_id}


@app.post("/api/registrations", status_code=201)
def register_for_retreat(payload: RegistrationCreate, user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    _sync_sales_windows(db)
    retreat = db.scalar(select(Retreat).where(Retreat.id == payload.retreat_id).with_for_update())
    if not retreat or retreat.status != RetreatStatus.published or not retreat.sales_open: raise HTTPException(400, "This retreat is not open for registration")
    assigned_courses = db.scalar(select(func.count(RetreatCourse.id)).where(RetreatCourse.retreat_id == retreat.id)) or 0
    global_courses = db.scalar(select(func.count(Course.id)).where(Course.is_active.is_(True))) or 0
    if assigned_courses or global_courses:
        course_query = select(Course).join(RetreatCourse, RetreatCourse.course_id == Course.id).where(RetreatCourse.retreat_id == retreat.id, Course.name == payload.course_of_study, Course.is_active.is_(True)) if assigned_courses else select(Course).where(Course.name == payload.course_of_study, Course.is_active.is_(True))
        if not db.scalar(course_query): raise HTTPException(422, "Select an active course option for this retreat")
    now = site_now()
    if retreat.sales_opens_at and now < retreat.sales_opens_at: raise HTTPException(400, "Ticket sales have not opened yet")
    if retreat.sales_closes_at and now > retreat.sales_closes_at: raise HTTPException(400, "Ticket sales have closed")
    existing_registration = db.scalar(select(Registration).where(Registration.attendee_id == user.id, Registration.retreat_id == retreat.id))
    if existing_registration and existing_registration.status != "failed": raise HTTPException(409, "You already registered for this retreat")
    reserved = db.scalar(select(func.count(Registration.id)).where(Registration.retreat_id == retreat.id, Registration.status.in_(["pending", "paid"]))) or 0
    if reserved >= retreat.capacity: raise HTTPException(409, "This retreat is sold out")
    registration = existing_registration or Registration(attendee_id=user.id, retreat_id=retreat.id, course_snapshot=payload.course_of_study)
    registration.course_snapshot = payload.course_of_study
    registration.status = "pending"
    db.add(registration); db.flush()
    if retreat.is_free or retreat.price_kes == 0:
        profile = db.scalar(select(AttendeeProfile).where(AttendeeProfile.user_id == user.id))
        if not profile: raise HTTPException(422, "Complete your attendee profile before registering")
        registration.status = "paid"
        ticket = Ticket(registration_id=registration.id, attendee_id=user.id, retreat_id=retreat.id, ticket_number=f"RT-{secrets.token_hex(5).upper()}", qr_token=secrets.token_urlsafe(32), attendee_name_snapshot=profile.full_name, course_snapshot=registration.course_snapshot, retreat_title_snapshot=retreat.title, retreat_date_snapshot=retreat.starts_at, price_snapshot=0, mpesa_receipt_snapshot=None)
        db.add(ticket)
        db.add(Notification(kind="registration.confirmed", title="Free registration confirmed", body=f"Your free ticket for {retreat.title} is ready."))
        db.add(ActivityLog(user_id=user.id, action="registration.free_confirmed", record_type="registration", record_id=str(registration.id)))
        db.commit()
        return {"registration_id": registration.id, "ticket_number": ticket.ticket_number, "status": "confirmed", "provider": "free", "message": "Registration confirmed. Your QR ticket is ready."}
    if not payload.mpesa_phone:
        raise HTTPException(422, "An M-Pesa phone number is required for paid events")
    old_payment = db.scalar(select(Payment).where(Payment.registration_id == registration.id).order_by(Payment.id.desc()))
    if old_payment:
        payment = old_payment
        payment.attendee_id = user.id
        payment.retreat_id = retreat.id
        payment.expected_amount = retreat.price_kes
        payment.phone_number = payload.mpesa_phone
        payment.paid_amount = None
        payment.mpesa_receipt = None
        payment.status = "pending"
        payment.callback_at = None
        payment.error_detail = None
        payment.transaction_reference = f"RET-{secrets.token_hex(8).upper()}"
    else:
        payment = Payment(registration_id=registration.id, attendee_id=user.id, retreat_id=retreat.id, expected_amount=retreat.price_kes, phone_number=payload.mpesa_phone, transaction_reference=f"RET-{secrets.token_hex(8).upper()}")
    db.add(payment); db.add(Notification(kind="registration.created", title="New registration", body=f"A new registration was created for {retreat.title}.")); db.add(Notification(kind="payment.pending", title="Payment awaiting verification", body=f"A payment request was created for {retreat.title}.")); db.commit(); db.refresh(payment)
    try:
        response = initiate_stk(phone_number=payload.mpesa_phone, amount=retreat.price_kes, account_reference=payment.transaction_reference, description=f"RETUNORI {retreat.title}")
        payment.transaction_reference = response.get("CheckoutRequestID", payment.transaction_reference); db.commit()
        return {"registration_id": registration.id, "payment_id": payment.id, "status": "pending", "provider": "daraja", "message": "STK Push sent. Complete payment on your phone; your ticket is issued only after callback verification."}
    except DarajaNotConfigured:
        payment.status = "failed"
        payment.error_detail = "Daraja is not configured on this environment"
        registration.status = "failed"
        db.add(Notification(kind="payment.failed", title="Payment could not be started", body=f"Payment setup is unavailable for {retreat.title}."))
        db.commit()
        raise HTTPException(503, "Daraja is not configured on this environment")
    except (httpx.HTTPError, DarajaResponseError):
        payment.status = "failed"
        payment.error_detail = "Daraja could not start the payment request"
        registration.status = "failed"
        db.add(Notification(kind="payment.failed", title="Payment could not be started", body=f"Daraja could not start payment for {retreat.title}."))
        db.commit()
        raise HTTPException(502, "Daraja could not be reached")


@app.post("/api/payments/{payment_id}/initiate")
def initiate_payment(payment_id: int, user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    payment = db.scalar(select(Payment).where(Payment.id == payment_id, Payment.attendee_id == user.id))
    if not payment: raise HTTPException(404, "Payment not found")
    if payment.status == "successful": raise HTTPException(409, "Payment is already successful")
    if payment.status == "pending" and payment.callback_at is None and payment.error_detail is None:
        try:
            response = initiate_stk(phone_number=payment.phone_number, amount=payment.expected_amount, account_reference=payment.transaction_reference, description="RETUNORI retreat ticket")
            payment.transaction_reference = response.get("CheckoutRequestID", payment.transaction_reference); db.commit()
            return {"status": "pending", "provider": "daraja", "checkout_request_id": payment.transaction_reference}
        except DarajaNotConfigured: raise HTTPException(503, "Daraja is not configured")
        except (httpx.HTTPError, DarajaResponseError): raise HTTPException(502, "Daraja could not be reached")
    raise HTTPException(409, "This payment has already been resolved or is awaiting callback")


@app.get("/api/payments/{payment_id}")
def payment_status(payment_id: int, user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    payment = db.scalar(select(Payment).where(Payment.id == payment_id, Payment.attendee_id == user.id))
    if not payment: raise HTTPException(404, "Payment not found")
    ticket = db.scalar(select(Ticket).where(Ticket.registration_id == payment.registration_id))
    return {"id": payment.id, "status": payment.status, "receipt": payment.mpesa_receipt, "error_detail": payment.error_detail, "ticket_number": ticket.ticket_number if ticket else None}


@app.post("/api/payments/daraja/callback")
@limiter.limit("60/minute")
def daraja_callback(request: Request, payload: dict, callback_secret: str = Query(default=""), db: Session = Depends(get_db)):
    """Daraja's adapter must call this endpoint only after authenticating the provider request."""
    settings = get_settings()
    if not settings.daraja_callback_secret and settings.daraja_consumer_key and settings.daraja_callback_url:
        raise HTTPException(503, "Daraja callback authentication is not configured")
    if settings.daraja_callback_secret and not secrets.compare_digest(callback_secret, settings.daraja_callback_secret):
        raise HTTPException(401, "Invalid callback authentication")
    callback = payload.get("Body", {}).get("stkCallback", {})
    if callback:
        metadata = {item.get("Name"): item.get("Value") for item in callback.get("CallbackMetadata", {}).get("Item", [])}
        normalized = {"checkout_reference": callback.get("CheckoutRequestID"), "result_code": callback.get("ResultCode"), "result_description": callback.get("ResultDesc"), "mpesa_receipt": metadata.get("MpesaReceiptNumber"), "amount": metadata.get("Amount")}
    else:
        normalized = payload
    checkout_reference = normalized.get("checkout_reference")
    try:
        result_code = int(normalized.get("result_code"))
    except (TypeError, ValueError):
        raise HTTPException(422, "Callback result code is invalid")
    result_description = normalized.get("result_description")
    amount = normalized.get("amount")
    try:
        amount = int(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None
    receipt = normalized.get("mpesa_receipt")
    receipt = str(receipt).strip() if receipt is not None else None
    payment = db.scalar(select(Payment).where(Payment.transaction_reference == checkout_reference).with_for_update())
    db.add(PaymentCallback(payment_id=payment.id if payment else None, checkout_reference=checkout_reference or "unknown", result_code=result_code if result_code is not None else -1, raw_payload=json.dumps(payload)))
    if not payment: db.commit(); return {"accepted": True}
    if payment.status == "successful": db.commit(); return {"accepted": True, "duplicate": True}
    payment.callback_at = datetime.utcnow()
    if result_code != 0:
        descriptions = {
            1032: "Payment cancelled. You can try again.",
            1037: "The M-Pesa prompt timed out. Please try again.",
            2001: "Incorrect M-Pesa PIN. Please try again.",
            1: "Payment failed. Please try again.",
            1019: "The M-Pesa request expired. Please try again.",
        }
        payment.status = "failed"
        payment.error_detail = descriptions.get(int(result_code), result_description or "Payment failed. Please try again.")
        registration = db.get(Registration, payment.registration_id)
        if registration: registration.status = "failed"
        db.add(Notification(kind="payment.failed", title="Payment failed", body=f"A payment attempt for payment {payment.id} failed.")); db.commit(); return {"accepted": True, "status": "failed"}
    receipt_owner = db.scalar(select(Payment).where(Payment.mpesa_receipt == receipt, Payment.id != payment.id)) if receipt else None
    if receipt_owner:
        payment.status = "pending"
        payment.error_detail = "M-Pesa receipt has already been used"
        db.commit()
        raise HTTPException(422, "Callback receipt has already been used")
    if amount != payment.expected_amount or not receipt:
        payment.status = "pending"; payment.error_detail = "Callback failed amount or receipt validation"; db.commit(); raise HTTPException(422, "Callback could not be verified")
    payment.status = "successful"; payment.paid_amount = amount; payment.mpesa_receipt = receipt
    registration = db.get(Registration, payment.registration_id); retreat = db.get(Retreat, payment.retreat_id); profile = db.scalar(select(AttendeeProfile).where(AttendeeProfile.user_id == payment.attendee_id))
    ticket = db.scalar(select(Ticket).where(Ticket.registration_id == registration.id))
    if not ticket:
        ticket = Ticket(registration_id=registration.id, attendee_id=payment.attendee_id, retreat_id=retreat.id, ticket_number=f"RT-{secrets.token_hex(5).upper()}", qr_token=secrets.token_urlsafe(32), attendee_name_snapshot=profile.full_name, course_snapshot=registration.course_snapshot, retreat_title_snapshot=retreat.title, retreat_date_snapshot=retreat.starts_at, price_snapshot=payment.expected_amount, mpesa_receipt_snapshot=payment.mpesa_receipt)
        db.add(ticket)
    registration.status = "paid"
    db.add(Notification(kind="payment.successful", title="Successful payment", body=f"Payment verified for {retreat.title}."))
    db.add(ActivityLog(user_id=payment.attendee_id, action="payment.verified", record_type="payment", record_id=str(payment.id)))
    if (db.scalar(select(func.count(Ticket.id)).where(Ticket.retreat_id == retreat.id)) or 0) + 1 >= retreat.capacity:
        retreat.sales_open = False
        db.add(Notification(kind="retreat.sold_out", title="Retreat sold out", body=f"{retreat.title} has reached capacity."))
    elif (retreat.capacity - (db.scalar(select(func.count(Ticket.id)).where(Ticket.retreat_id == retreat.id)) or 0)) <= max(1, round(retreat.capacity * 0.1)):
        db.add(Notification(kind="retreat.low_capacity", title="Low retreat capacity", body=f"{retreat.title} has limited places remaining."))
    db.commit()
    return {"accepted": True, "status": "successful", "ticket_number": ticket.ticket_number}


@app.get("/api/me/tickets")
def my_tickets(user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    return [{"ticket_number": t.ticket_number, "retreat_title": t.retreat_title_snapshot, "retreat_date": t.retreat_date_snapshot, "course": t.course_snapshot, "price_kes": t.price_snapshot, "payment_status": "successful", "mpesa_receipt": t.mpesa_receipt_snapshot} for t in db.scalars(select(Ticket).where(Ticket.attendee_id == user.id)).all()]


@app.get("/api/me/payments")
def my_payments(user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    return [{"transaction_reference": p.transaction_reference, "expected_amount": p.expected_amount, "paid_amount": p.paid_amount, "status": p.status, "receipt": p.mpesa_receipt, "requested_at": p.requested_at, "callback_at": p.callback_at} for p in db.scalars(select(Payment).where(Payment.attendee_id == user.id).order_by(Payment.requested_at.desc())).all()]


@app.get("/api/me/tickets/{ticket_number}/pdf")
def download_ticket(ticket_number: str, user: User = Depends(require_roles(Role.attendee)), db: Session = Depends(get_db)):
    ticket = db.scalar(select(Ticket).where(Ticket.ticket_number == ticket_number, Ticket.attendee_id == user.id))
    if not ticket: raise HTTPException(404, "Ticket not found")
    return StreamingResponse(ticket_pdf(ticket), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{ticket.ticket_number}.pdf"'})


@app.post("/api/staff/check-in")
def staff_check_in(payload: CheckInRequest, user: User = Depends(require_roles(Role.staff, Role.admin)), db: Session = Depends(get_db)):
    assigned = user.role == Role.admin or db.scalar(select(StaffRetreatAssignment).where(StaffRetreatAssignment.staff_id == user.id, StaffRetreatAssignment.retreat_id == payload.retreat_id))
    if not assigned: raise HTTPException(403, "You are not assigned to this retreat")
    if payload.method == "name":
        matches = db.scalars(select(Ticket).where(Ticket.attendee_name_snapshot.ilike(f"%{payload.value}%"), Ticket.retreat_id == payload.retreat_id).limit(10)).all()
        if len(matches) > 1: return {"status": "multiple_matches", "matches": [{"ticket_number": item.ticket_number, "attendee_name": item.attendee_name_snapshot, "course": item.course_snapshot} for item in matches]}
        ticket = matches[0] if matches else None
    else:
        ticket = db.scalar(select(Ticket).where((Ticket.ticket_number == payload.value) | (Ticket.qr_token == payload.value), Ticket.retreat_id == payload.retreat_id))
    if not ticket:
        db.add(ScanAttempt(retreat_id=payload.retreat_id, staff_id=user.id, method=payload.method, result="invalid")); db.commit(); raise HTTPException(404, "Invalid ticket")
    retreat = db.get(Retreat, ticket.retreat_id)
    payment = db.scalar(select(Payment).where(Payment.registration_id == ticket.registration_id, Payment.status == "successful"))
    if not retreat.is_free and not payment:
        db.add(ScanAttempt(ticket_id=ticket.id, retreat_id=payload.retreat_id, staff_id=user.id, method=payload.method, result="unpaid")); db.commit(); raise HTTPException(409, "Payment has not been successfully verified")
    existing = db.scalar(select(CheckIn).where(CheckIn.ticket_id == ticket.id))
    if existing:
        db.add(ScanAttempt(ticket_id=ticket.id, retreat_id=payload.retreat_id, staff_id=user.id, method=payload.method, result="already_checked_in")); db.add(Notification(kind="checkin.repeated_scan", title="Repeated ticket scan", body=f"Ticket {ticket.ticket_number} was scanned again.")); db.add(ActivityLog(user_id=user.id, action="checkin.repeated_scan", record_type="ticket", record_id=str(ticket.id))); db.commit()
        original_staff = db.get(User, existing.staff_id)
        raise HTTPException(409, {"status": "ALREADY CHECKED IN", "checked_in_at": existing.checked_in_at.isoformat(), "staff_email": original_staff.email if original_staff else None})
    checkin = CheckIn(ticket_id=ticket.id, retreat_id=payload.retreat_id, staff_id=user.id, method=payload.method)
    db.add(checkin); db.add(ScanAttempt(ticket_id=ticket.id, retreat_id=payload.retreat_id, staff_id=user.id, method=payload.method, result="success")); db.add(ActivityLog(user_id=user.id, action="checkin.success", record_type="ticket", record_id=str(ticket.id), details=payload.method)); db.commit()
    return {"status": "success", "ticket_number": ticket.ticket_number, "attendee_name": ticket.attendee_name_snapshot, "course": ticket.course_snapshot, "payment_status": "free" if retreat.is_free else payment.status, "checked_in_at": checkin.checked_in_at}


@app.get("/api/staff/attendance")
def staff_attendance(user: User = Depends(require_roles(Role.staff, Role.admin)), retreat_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    query = select(CheckIn)
    if user.role == Role.staff:
        assigned = select(StaffRetreatAssignment.retreat_id).where(StaffRetreatAssignment.staff_id == user.id)
        query = query.where(CheckIn.retreat_id.in_(assigned))
    if retreat_id is not None:
        query = query.where(CheckIn.retreat_id == retreat_id)
    records = db.scalars(query).all()
    return {"checked_in": len(records), "recent": [{"retreat_id": item.retreat_id, "method": item.method, "checked_in_at": item.checked_in_at, "staff_id": item.staff_id} for item in records[-50:]]}


@app.get("/api/staff/scan-history")
def staff_scan_history(user: User = Depends(require_roles(Role.staff, Role.admin)), db: Session = Depends(get_db)):
    query = select(ScanAttempt).where(ScanAttempt.staff_id == user.id).order_by(ScanAttempt.attempted_at.desc()).limit(100)
    return db.scalars(query).all()
