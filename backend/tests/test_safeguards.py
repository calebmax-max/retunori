import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.auth import hash_password
from app.db import SessionLocal
from app.main import app
from app.models import AttendeeProfile, CheckIn, Payment, Registration, Retreat, RetreatStatus, Role, StaffRetreatAssignment, Ticket, User


def test_multiple_retreats_can_open_sales():
    suffix = uuid.uuid4().hex
    db = SessionLocal()
    admin = User(email=f"admin-{suffix}@example.com", password_hash=hash_password("strong-pass-123"), role=Role.admin)
    open_retreat = Retreat(slug=f"open-{suffix}", title=f"Open {suffix}", description="Test", venue="Nairobi", starts_at=datetime.utcnow()+timedelta(days=5), ends_at=datetime.utcnow()+timedelta(days=6), price_kes=100, capacity=10, status=RetreatStatus.published, sales_open=True)
    db.add_all([admin, open_retreat]); db.commit(); db.refresh(admin); db.close()
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"email": admin.email, "password": "strong-pass-123"}).json()["access_token"]
        response = client.post("/api/admin/retreats", json={"slug": f"second-{suffix}", "title": f"Second {suffix}", "description": "Test", "venue": "Nairobi", "starts_at": (datetime.utcnow()+timedelta(days=7)).isoformat(), "ends_at": (datetime.utcnow()+timedelta(days=8)).isoformat(), "price_kes": 100, "capacity": 10, "status": "published", "sales_open": True}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 201


def test_unpaid_ticket_cannot_check_in():
    suffix = uuid.uuid4().hex
    db = SessionLocal()
    attendee = User(email=f"unpaid-attendee-{suffix}@example.com", password_hash=hash_password("strong-pass-123"), role=Role.attendee); attendee.attendee_profile = AttendeeProfile(full_name="Unpaid Attendee", phone="0712345678", course_of_study="Testing")
    staff = User(email=f"unpaid-staff-{suffix}@example.com", password_hash=hash_password("strong-pass-123"), role=Role.staff)
    retreat = Retreat(slug=f"unpaid-{suffix}", title=f"Unpaid {suffix}", description="Test", venue="Nairobi", starts_at=datetime.utcnow()+timedelta(days=5), ends_at=datetime.utcnow()+timedelta(days=6), price_kes=2500, capacity=5, status=RetreatStatus.published, sales_open=True)
    db.add_all([attendee, staff, retreat]); db.flush()
    registration = Registration(attendee_id=attendee.id, retreat_id=retreat.id, course_snapshot="Testing", status="pending"); db.add(registration); db.flush()
    db.add(Payment(registration_id=registration.id, attendee_id=attendee.id, retreat_id=retreat.id, expected_amount=2500, phone_number="0712345678", transaction_reference=f"RET-{suffix}", status="pending"))
    ticket = Ticket(registration_id=registration.id, attendee_id=attendee.id, retreat_id=retreat.id, ticket_number=f"RT-{suffix[:8]}", qr_token=f"opaque-{suffix}", attendee_name_snapshot="Unpaid Attendee", course_snapshot="Testing", retreat_title_snapshot=retreat.title, retreat_date_snapshot=retreat.starts_at, price_snapshot=2500); db.add(ticket)
    db.add(StaffRetreatAssignment(staff_id=staff.id, retreat_id=retreat.id)); db.commit(); staff_email = staff.email; ticket_number = ticket.ticket_number; retreat_id = retreat.id; db.close()
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"email": staff_email, "password": "strong-pass-123"}).json()["access_token"]
        response = client.post("/api/staff/check-in", json={"retreat_id": retreat_id, "value": ticket_number, "method": "manual"}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 409
        db = SessionLocal(); assert db.query(CheckIn).filter(CheckIn.ticket_id == ticket.id).count() == 0; db.close()
