from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from .models import Role, RetreatStatus


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    course_of_study: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: Role
    full_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    user: UserOut


class RetreatImageOut(BaseModel):
    id: int
    url: str
    alt_text: str
    sort_order: int
    model_config = ConfigDict(from_attributes=True)


class CourseOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class RetreatOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    venue: str
    location_url: str | None
    starts_at: datetime
    ends_at: datetime
    price_kes: int
    is_free: bool
    capacity: int
    status: RetreatStatus
    sales_open: bool
    sales_opens_at: datetime | None
    sales_closes_at: datetime | None
    poster_url: str | None
    images: list[RetreatImageOut] = []
    course_options: list[CourseOut] = []
    tickets_sold: int = 0
    remaining_capacity: int = 0
    model_config = ConfigDict(from_attributes=True)


class RetreatCreate(BaseModel):
    slug: str | None = Field(default=None, min_length=3, max_length=180, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=2)
    venue: str = Field(min_length=2, max_length=180)
    location_url: str | None = None
    starts_at: datetime
    ends_at: datetime
    price_kes: int = Field(ge=0)
    is_free: bool = False
    capacity: int = Field(gt=0)
    status: RetreatStatus = RetreatStatus.draft
    sales_open: bool = False
    sales_opens_at: datetime | None = None
    sales_closes_at: datetime | None = None


class RetreatUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    venue: str | None = None
    location_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    price_kes: int | None = Field(default=None, ge=0)
    is_free: bool | None = None
    capacity: int | None = Field(default=None, gt=0)
    status: RetreatStatus | None = None
    sales_open: bool | None = None
    sales_opens_at: datetime | None = None
    sales_closes_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class RegistrationCreate(BaseModel):
    retreat_id: int
    course_of_study: str = Field(min_length=2, max_length=160)
    mpesa_phone: str | None = Field(default=None, min_length=7, max_length=40)


class CheckInRequest(BaseModel):
    retreat_id: int
    value: str = Field(min_length=2)
    method: str = "manual"


class DarajaCallback(BaseModel):
    checkout_reference: str
    result_code: int
    mpesa_receipt: str | None = None
    amount: int | None = None


class ContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    message: str = Field(min_length=5, max_length=5000)


class StaffCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=40)
    course_of_study: str = Field(min_length=2, max_length=160)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class CourseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=2)
    is_pinned: bool = False
    is_published: bool = True
    retreat_id: int | None = None
    expires_at: datetime | None = None
    image_urls: list[str] = Field(default_factory=list)


class AnnouncementUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=2)
    is_pinned: bool = False
    is_published: bool = True


class LegalPageUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=2)


class HomepageUpdate(BaseModel):
    headline: str = Field(min_length=2, max_length=220)
    introduction: str = Field(min_length=2)
    support_email: EmailStr
    support_phone: str = ""


class FeaturedUpdate(BaseModel):
    retreat_ids: list[int] = []


class SeoUpdate(BaseModel):
    page_title: str = Field(min_length=2, max_length=180)
    meta_description: str = Field(min_length=2, max_length=320)
    social_image_url: str | None = None
