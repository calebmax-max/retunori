import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.auth import hash_password
from app.db import SessionLocal
from app.main import app
from app.models import AttendeeProfile, CheckIn, Payment, Registration, Retreat, RetreatStatus, Role, StaffRetreatAssignment, Ticket, User


def test_assigned_staff_checkin_is_single_use():
    suffix = uuid.uuid4().hex
    db = SessionLocal()
    attendee = User(email=f"attendee-{suffix}@example.com", password_hash=hash_password("strong-pass-123"), role=Role.attendee); attendee.attendee_profile = AttendeeProfile(full_name="Checkin Attendee", phone="0712345678", course_of_study="Testing")
    staff = User(email=f"staff-{suffix}@example.com", password_hash=hash_password("strong-pass-123"), role=Role.staff)
    retreat = Retreat(slug=f"checkin-{suffix}", title=f"Checkin {suffix}", description="Test", venue="Nairobi", starts_at=datetime.utcnow()+timedelta(days=5), ends_at=datetime.utcnow()+timedelta(days=6), price_kes=2500, capacity=5, status=RetreatStatus.published, sales_open=True)
    db.add_all([attendee, staff, retreat]); db.flush()
    registration = Registration(attendee_id=attendee.id, retreat_id=retreat.id, course_snapshot="Testing", status="paid"); db.add(registration); db.flush()
    payment = Payment(registration_id=registration.id, attendee_id=attendee.id, retreat_id=retreat.id, expected_amount=2500, paid_amount=2500, phone_number="0712345678", transaction_reference=f"RET-{suffix}", mpesa_receipt=f"MPESA-{suffix}", status="successful"); db.add(payment)
    ticket = Ticket(registration_id=registration.id, attendee_id=attendee.id, retreat_id=retreat.id, ticket_number=f"RT-{suffix[:8]}", qr_token=f"opaque-{suffix}", attendee_name_snapshot="Checkin Attendee", course_snapshot="Testing", retreat_title_snapshot=retreat.title, retreat_date_snapshot=retreat.starts_at, price_snapshot=2500); db.add(ticket)
    db.add(StaffRetreatAssignment(staff_id=staff.id, retreat_id=retreat.id)); db.commit(); staff_email = staff.email; ticket_number = ticket.ticket_number; retreat_id = retreat.id; db.close()
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"email": staff_email, "password":"strong-pass-123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        first = client.post("/api/staff/check-in", json={"retreat_id":retreat_id,"value":ticket_number,"method":"manual"}, headers=headers)
        assert first.status_code == 200
        duplicate = client.post("/api/staff/check-in", json={"retreat_id":retreat_id,"value":ticket_number,"method":"manual"}, headers=headers)
        assert duplicate.status_code == 409
        db = SessionLocal(); assert db.query(CheckIn).filter(CheckIn.ticket_id == ticket.id).count() == 1; db.close()
