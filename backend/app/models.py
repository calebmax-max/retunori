from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Role(str, Enum):
    attendee = "attendee"
    staff = "staff"
    admin = "admin"


class RetreatStatus(str, Enum):
    draft = "draft"
    published = "published"
    scheduled = "scheduled"
    archived = "archived"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SqlEnum(Role), default=Role.attendee, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    attendee_profile: Mapped[Optional["AttendeeProfile"]] = relationship(back_populates="user", uselist=False)


class AttendeeProfile(Base):
    __tablename__ = "attendee_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    course_of_study: Mapped[str] = mapped_column(String(160))
    user: Mapped[User] = relationship(back_populates="attendee_profile")


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    retreat_links: Mapped[list["RetreatCourse"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class Retreat(Base):
    __tablename__ = "retreats"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    venue: Mapped[str] = mapped_column(String(180))
    location_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    price_kes: Mapped[int] = mapped_column(Integer)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[RetreatStatus] = mapped_column(SqlEnum(RetreatStatus), default=RetreatStatus.draft, index=True)
    sales_open: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_opens_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sales_closes_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    images: Mapped[list["RetreatImage"]] = relationship(back_populates="retreat", cascade="all, delete-orphan", order_by="RetreatImage.sort_order")
    course_links: Mapped[list["RetreatCourse"]] = relationship(back_populates="retreat", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("title", "starts_at", name="uq_retreat_title_date"),)


class RetreatImage(Base):
    __tablename__ = "retreat_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    alt_text: Mapped[str] = mapped_column(String(180), default="RETUNORI retreat image")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    retreat: Mapped[Retreat] = relationship(back_populates="images")


class RetreatCourse(Base):
    __tablename__ = "retreat_courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    retreat: Mapped[Retreat] = relationship(back_populates="course_links")
    course: Mapped[Course] = relationship(back_populates="retreat_links")
    __table_args__ = (UniqueConstraint("retreat_id", "course_id", name="uq_retreat_course"),)


class Registration(Base):
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    attendee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), index=True)
    course_snapshot: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("attendee_id", "retreat_id", name="uq_registration_attendee_retreat"),)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), unique=True)
    attendee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), index=True)
    expected_amount: Mapped[int] = mapped_column(Integer)
    paid_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone_number: Mapped[str] = mapped_column(String(40))
    transaction_reference: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    callback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), unique=True)
    attendee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), index=True)
    ticket_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    qr_token: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    attendee_name_snapshot: Mapped[str] = mapped_column(String(160))
    course_snapshot: Mapped[str] = mapped_column(String(160))
    retreat_title_snapshot: Mapped[str] = mapped_column(String(180))
    retreat_date_snapshot: Mapped[datetime] = mapped_column(DateTime)
    price_snapshot: Mapped[int] = mapped_column(Integer)
    mpesa_receipt_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CheckIn(Base):
    __tablename__ = "check_ins"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), unique=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(20))
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScanAttempt(Base):
    __tablename__ = "scan_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"), nullable=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(40))
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StaffRetreatAssignment(Base):
    __tablename__ = "staff_retreat_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), index=True)
    __table_args__ = (UniqueConstraint("staff_id", "retreat_id", name="uq_staff_retreat"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    record_type: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentCallback(Base):
    __tablename__ = "payment_callbacks"
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True, index=True)
    checkout_reference: Mapped[str] = mapped_column(String(120), index=True)
    result_code: Mapped[int] = mapped_column(Integer)
    raw_payload: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    retreat_id: Mapped[int | None] = mapped_column(ForeignKey("retreats.id"), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    image_urls: Mapped[str] = mapped_column(Text, default="[]")


class ContactSubmission(Base):
    __tablename__ = "contact_submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="new")


class LegalPage(Base):
    __tablename__ = "legal_pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HomepageContent(Base):
    __tablename__ = "homepage_content"
    id: Mapped[int] = mapped_column(primary_key=True)
    headline: Mapped[str] = mapped_column(String(220), default="Make room for what matters.")
    introduction: Mapped[str] = mapped_column(Text, default="Intentional retreats for meaningful connection.")
    support_email: Mapped[str] = mapped_column(String(320), default="hello@retunori.com")
    support_phone: Mapped[str] = mapped_column(String(40), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeaturedRetreat(Base):
    __tablename__ = "featured_retreats"
    id: Mapped[int] = mapped_column(primary_key=True)
    retreat_id: Mapped[int] = mapped_column(ForeignKey("retreats.id"), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Backup(Base):
    __tablename__ = "backups"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="complete")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SeoMetadata(Base):
    __tablename__ = "seo_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    retreat_id: Mapped[int | None] = mapped_column(ForeignKey("retreats.id"), unique=True, nullable=True)
    path: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    page_title: Mapped[str] = mapped_column(String(180))
    meta_description: Mapped[str] = mapped_column(String(320))
    social_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
