FROM python:3.12-slim

WORKDIR /app

# Instala dependencias primero (mejor cacheo de capas)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      "fastapi>=0.115" "uvicorn[standard]>=0.32" "sqlalchemy>=2.0" \
      "alembic>=1.14" "psycopg[binary]>=3.2" "pydantic>=2.10" "pydantic-settings>=2.7"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
