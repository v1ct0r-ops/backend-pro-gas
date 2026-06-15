from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.models import Usuario
from database import SessionLocal


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))

        if not email or not password:
            return False

        db = SessionLocal()
        try:
            user = db.query(Usuario).filter(Usuario.email == email).first()
        finally:
            db.close()

        if not user:
            return False
        if not user.estado:
            return False
        if user.rol != "super_admin":
            return False
        if not verify_password(password, user.password_hash):
            return False

        token = create_access_token({"sub": user.email})
        request.session.update({"admin_token": token})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("admin_token")
        if not token:
            return False
        try:
            decode_access_token(token)
            return True
        except Exception:
            return False
