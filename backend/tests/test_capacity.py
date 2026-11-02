import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.main import app
from app.models import Payment, Retreat, RetreatStatus


def test_pending_registration_reserves_capacity_until_failed_callback():
    suffix = uuid.uuid4().hex
    db = SessionLocal()
    retreat = Retreat(slug=f"capacity-{suffix}", title=f"Capacity {suffix}", description="Test", venue="Nairobi", starts_at=datetime.utcnow() + timedelta(days=5), ends_at=datetime.utcnow() + timedelta(days=6), price_kes=2500, capacity=1, status=RetreatStatus.published, sales_open=True)
    db.add(retreat); db.commit(); db.refresh(retreat); retreat_id = retreat.id; db.close()
    first = {"full_name": "First Attendee", "email": f"first-{suffix}@example.com", "phone": "0712345678", "course_of_study": "Testing", "password": "strong-pass-123"}
    second = {"full_name": "Second Attendee", "email": f"second-{suffix}@example.com", "phone": "0712345679", "course_of_study": "Testing", "password": "strong-pass-123"}
    with TestClient(app) as client:
        first_token = client.post("/api/auth/register", json=first).json()["access_token"]
        payment = client.post("/api/registrations", json={"retreat_id": retreat_id, "course_of_study": "Testing", "mpesa_phone": first["phone"]}, headers={"Authorization": f"Bearer {first_token}"}).json()
        second_token = client.post("/api/auth/register", json=second).json()["access_token"]
        blocked = client.post("/api/registrations", json={"retreat_id": retreat_id, "course_of_study": "Testing", "mpesa_phone": second["phone"]}, headers={"Authorization": f"Bearer {second_token}"})
        assert blocked.status_code == 409
        db = SessionLocal(); transaction = db.get(Payment, payment["payment_id"]); reference = transaction.transaction_reference; db.close()
        failed = client.post("/api/payments/daraja/callback", json={"checkout_reference": reference, "result_code": 1})
        assert failed.status_code == 200
        available = client.post("/api/registrations", json={"retreat_id": retreat_id, "course_of_study": "Testing", "mpesa_phone": second["phone"]}, headers={"Authorization": f"Bearer {second_token}"})
        assert available.status_code == 201
