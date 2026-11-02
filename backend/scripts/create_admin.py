"""Create the first RETUNORI administrator without exposing account creation over HTTP."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Role, User


def main():
    parser = argparse.ArgumentParser(description="Create a RETUNORI administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True, help="Use a strong password; it is not stored in shell history by the application")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = args.email.lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise SystemExit("An account with that email already exists")
        admin = User(email=email, password_hash=hash_password(args.password), role=Role.admin)
        db.add(admin); db.commit()
        print(f"Administrator created: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
