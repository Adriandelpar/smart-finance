FROM python:3.12-slim

# Sin .pyc y con logs al momento (útil en `docker compose logs -f`)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Madrid

WORKDIR /app

# Primero solo las dependencias: así Docker cachea esta capa
# y no reinstala nada si solo cambia el código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# No ejecutar como root dentro del contenedor
RUN useradd --create-home --uid 1000 finanzas
USER finanzas

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud')"

# gunicorn: servidor de producción (el `flask run` es solo para desarrollo).
# Un solo proceso con 4 hilos: así la caché de Notion (y la demo en memoria)
# es una sola y todos los cambios se ven al momento. Para uso personal sobra.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "app:create_app()"]
