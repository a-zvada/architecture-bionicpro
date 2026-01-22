from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import httpx
from typing import Dict, Any, List
from clickhouse_driver import Client
from datetime import datetime
import os

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

# Настройки ClickHouse — берём из переменных окружения
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "bionic_data")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin")

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


def generate_pdf_report(email: str, telemetry_data: List[Dict]) -> BytesIO:
    """Генерирует PDF-отчёт с отдельной таблицей для каждого сенсора"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    styles = getSampleStyleSheet()
    elements = []

    # Заголовок отчёта
    elements.append(Paragraph(f"Sensors telemtry report for {email}", styles['Title']))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.5 * inch))

    if not telemetry_data:
        elements.append(Paragraph("No data for this user.", styles['Normal']))
    else:
        # Группируем данные по sensor_id
        from collections import defaultdict
        sensors_data = defaultdict(list)

        for row in telemetry_data:
            sensor_id = row.get('sensor_id', 'unknown')
            sensor_type = row.get('sensor_type', '—')
            key = f"{sensor_id} ({sensor_type})"
            sensors_data[key].append(row)

        # Для каждого сенсора создаём свою таблицу
        for sensor_key, data in sensors_data.items():
            elements.append(Paragraph(f"Sensor: {sensor_key}", styles['Heading2']))
            elements.append(Spacer(1, 0.2 * inch))

            # Подготавливаем данные для таблицы
            table_data = [["Timestamp", "Value"]]

            for row in data:
                recorded_at = row.get('recorded_at', '—')
                value = row.get('value', '—')
                table_data.append([recorded_at, str(value)])

            # Создаём таблицу
            from reportlab.platypus import Table, TableStyle
            t = Table(table_data, colWidths=[3.5*inch, 1.5*inch])

            # Стили таблицы
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 12),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))

            elements.append(t)
            elements.append(Spacer(1, 0.4 * inch))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def get_telemetry_data(email: str) -> List[Dict]:
    """
    Получает данные телеметрии для указанного пользователя по email.
    Возвращает список словарей с полями recorded_at и value.
    """
    try:
        client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB,
            secure=False
        )

        query = """
            SELECT 
                sensor_id,
                sensor_type,
                recorded_at,
                value
            FROM telemetry_analytics
            WHERE email = %(email)s
            ORDER BY recorded_at ASC
            LIMIT 100
        """

        result = client.execute(query, params={'email': email})

        # Преобразуем результат в удобный список словарей
        telemetry_data = [
            {
                "sensor_id": row[0],
                "sensor_type": row[1],
                "recorded_at": row[2],
                "value": row[3]
            }
            for row in result
        ]

        return telemetry_data

    except Exception as e:
        print(f"Ошибка при запросе к ClickHouse: {e}")
        return []

@app.options("/reports")
async def options_reports():
    return {"Allow": "GET, OPTIONS"}

@app.get("/reports")
async def get_report(user: dict = Depends(verify_token)):
    """
    Формирует и возвращает PDF-отчёт с данными телеметрии.
    """
    email = user.get("email", None)
    if not email:
        raise HTTPException(status_code=400, detail="E-mail не найден в токене")

    # Получаем данные из ClickHouse через отдельную функцию
    telemetry_data = get_telemetry_data(email)

    # Генерируем PDF
    pdf_buffer = generate_pdf_report(email, telemetry_data)

    headers = {
        "Content-Disposition": f"attachment; filename=report_{email.split('@')[0]}.pdf",
        "Content-Type": "application/pdf",
    }

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers=headers
    )