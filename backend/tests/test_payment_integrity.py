import uuid
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.main import app
from app.models import Retreat, RetreatStatus, Ticket, Payment
from datetime import datetime, timedelta
from sqlalchemy import select


def test_registration_stays_pending_until_verified_callback():
    slug = f"test-retreat-{uuid.uuid4().hex}"
    db = SessionLocal()
    retreat = Retreat(slug=slug, title=f"Integrity {slug}", description="Test", venue="Nairobi", starts_at=datetime.utcnow() + timedelta(days=30), ends_at=datetime.utcnow() + timedelta(days=31), price_kes=5000, capacity=10, status=RetreatStatus.published, sales_open=True)
    db.add(retreat); db.commit(); db.refresh(retreat); retreat_id = retreat.id; db.close()
    email = f"payment-{uuid.uuid4().hex}@example.com"
    account = {"full_name":"Payment Tester","email":email,"phone":"0712345678","course_of_study":"Testing","password":"strong-pass-123"}
    with TestClient(app) as client:
        token = client.post("/api/auth/register", json=account).json()["access_token"]
        response = client.post("/api/registrations", json={"retreat_id":retreat_id,"course_of_study":"Testing","mpesa_phone":"0712345678"}, headers={"Authorization":f"Bearer {token}"})
        assert response.status_code == 201
        payment_id = response.json()["payment_id"]
        db = SessionLocal(); payment = db.get(Payment, payment_id); assert payment.status == "pending"; assert db.scalar(select(Ticket).where(Ticket.registration_id == payment.registration_id)) is None; db.close()
        callback = client.post("/api/payments/daraja/callback", json={"checkout_reference":payment.transaction_reference,"result_code":0,"mpesa_receipt":"ABC123","amount":4999})
        assert callback.status_code == 422
        success = client.post("/api/payments/daraja/callback", json={"checkout_reference":payment.transaction_reference,"result_code":0,"mpesa_receipt":"ABC123","amount":5000})
        assert success.status_code == 200
        duplicate = client.post("/api/payments/daraja/callback", json={"Body":{"stkCallback":{"CheckoutRequestID":payment.transaction_reference,"ResultCode":0,"CallbackMetadata":{"Item":[{"Name":"Amount","Value":5000},{"Name":"MpesaReceiptNumber","Value":"ABC123"}]}}}})
        assert duplicate.status_code == 200 and duplicate.json().get("duplicate") is True
        db = SessionLocal(); assert db.query(Ticket).filter(Ticket.registration_id == payment.registration_id).count() == 1; db.close()
