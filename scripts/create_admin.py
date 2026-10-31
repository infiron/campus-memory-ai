"""Create an initial admin for a non-seeded database. Run from backend after installing dependencies."""
import getpass
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
if not BACKEND.is_dir():  # In the Docker image, /app/app is the importable backend package.
    BACKEND = PROJECT_ROOT
sys.path.insert(0, str(BACKEND))

from app.database import Base, engine, SessionLocal
from app.models import User
from app.security import hash_password


def main():
    username = os.getenv("INITIAL_ADMIN_USERNAME") or input("Admin username: ").strip()
    display = os.getenv("INITIAL_ADMIN_NAME") or input("Display name: ").strip() or "系统管理员"
    password = os.getenv("INITIAL_ADMIN_PASSWORD") or getpass.getpass("Strong password (minimum 14 characters): ")
    if len(password) < 14:
        raise SystemExit("Refusing to create admin: use at least 14 characters for the initial password.")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(User).filter(User.username == username).first():
            raise SystemExit("A user with that username already exists.")
        user = User(username=username, display_name=display, password_hash=hash_password(password), roles=["reader", "reviewer", "admin"], active=True)
        db.add(user)
        db.commit()
        print(f"Created administrator {username!r} with roles reader/reviewer/admin.")
        print("Store the credentials securely; the password is not printed.")

if __name__ == "__main__":
    main()
