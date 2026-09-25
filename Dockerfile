FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Librerías de sistema que necesitan mediapipe/opencv aunque se use la
# variante "headless" (no traen GUI, pero sí dependen de estas libs en runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# No requiere variables de entorno reales: todas tienen default seguro en
# settings.py y collectstatic no toca la base de datos.
# --upload-unhashed-files es necesario: django-cloudinary-storage reemplaza
# el comando collectstatic con una versión que, sin esa bandera, NO copia
# los archivos estáticos locales (asume que todo se sube a Cloudinary).
# Como acá Cloudinary solo se usa para media, no para estáticos, hace falta
# forzarlo así para que WhiteNoise tenga algo que servir.
RUN python manage.py collectstatic --noinput --upload-unhashed-files \
    && count=$(find staticfiles -type f | wc -l) \
    && echo "Archivos estáticos recolectados: $count" \
    && [ "$count" -gt 50 ]

EXPOSE 8000

CMD sh -c "python manage.py migrate --noinput && gunicorn EDUFLEX.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 120"
