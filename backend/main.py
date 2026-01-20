from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import httpx
from typing import Dict, Any

app = FastAPI(title="Reports Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],  # откуда приходит фронт
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],                                 # разрешаем GET и OPTIONS
    allow_headers=["Authorization", "Content-Type"],                  # нужные заголовки
    expose_headers=["Content-Disposition"],                           # чтобы frontend видел имя файла
    max_age=3600,
)

security = HTTPBearer()

# Настройки Keycloak (замените, если нужно)
KEYCLOAK_URL = "http://keycloak:8080"
REALM = "reports-realm"
JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"

jwks_cache: Dict[str, Any] = {}

async def get_jwks():
    global jwks_cache
    if not jwks_cache:
        async with httpx.AsyncClient() as client:
            resp = await client.get(JWKS_URL)
            resp.raise_for_status()
            jwks_cache = resp.json()
    return jwks_cache

async def get_public_key(kid: str):
    jwks = await get_jwks()
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return key
    raise HTTPException(status_code=401, detail="Public key not found")

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Invalid token header")

    public_key = await get_public_key(kid)

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="reports-frontend",
            options={"verify_exp": True, "verify_aud": True}
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def generate_pdf_stub(username: str = "Пользователь") -> BytesIO:
    """Генерирует простой PDF-заглушку"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 100, "Отчёт (заглушка)")

    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 150, f"Здравствуйте, {username}!")

    c.drawString(100, height - 200, "Это тестовый PDF-документ.")
    c.drawString(100, height - 230, "Реальный отчёт будет формироваться здесь.")
    c.drawString(100, height - 260, "Дата генерации: январь 2026")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


@app.options("/reports")
async def options_reports():
    return {"Allow": "GET, OPTIONS"}

@app.get("/reports")
async def get_report(user: dict = Depends(verify_token)):
    """
    Формирует и возвращает PDF-заглушку.
    Требует валидный Bearer-токен.
    """
    username = user.get("preferred_username", "Аноним")

    pdf_buffer = generate_pdf_stub(username)

    headers = {
        "Content-Disposition": f"attachment; filename=report_stub_{username}.pdf",
        "Content-Type": "application/pdf",
    }

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers=headers
    )