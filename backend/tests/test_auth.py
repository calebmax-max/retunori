import uuid
from fastapi.testclient import TestClient
from app.main import app


def test_attendee_registration_login_and_identity():
    email = f"test-{uuid.uuid4().hex}@example.com"
    payload = {"full_name": "Test Attendee", "email": email, "phone": "0712345678", "course_of_study": "Computer Science", "password": "strong-pass-123"}
    with TestClient(app) as client:
        registered = client.post("/api/auth/register", json=payload)
        assert registered.status_code == 201
        token = registered.json()["access_token"]
        identity = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert identity.status_code == 200
        assert identity.json()["email"] == email
        login = client.post("/api/auth/login", json={"email": email, "password": payload["password"]})
        assert login.status_code == 200


def test_attendee_cannot_access_admin_report():
    email = f"test-{uuid.uuid4().hex}@example.com"
    payload = {"full_name": "Restricted Attendee", "email": email, "phone": "0712345678", "course_of_study": "Design", "password": "strong-pass-123"}
    with TestClient(app) as client:
        token = client.post("/api/auth/register", json=payload).json()["access_token"]
        response = client.get("/api/admin/reports", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


def test_new_login_revokes_previous_session():
    email = f"test-{uuid.uuid4().hex}@example.com"
    payload = {"full_name": "Single Session", "email": email, "phone": "0712345678", "course_of_study": "Security", "password": "strong-pass-123"}
    with TestClient(app) as client:
        first = client.post("/api/auth/register", json=payload).json()["access_token"]
        second = client.post("/api/auth/login", json={"email": email, "password": payload["password"]}).json()["access_token"]
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {first}"}).status_code == 401
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 200
