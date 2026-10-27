FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# WeasyPrint (rapports PDF) : moteur de mise en page Pango et polices embarquées dans les PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-inter fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN useradd --create-home --uid 1000 solugation
COPY . .
# Fichiers statiques (admin, API) compilés dans l'image ; valeurs factices : rien n'est lu ni contacté ici.
RUN DJANGO_SECRET_KEY=construction DATABASE_URL=postgres://construction@localhost/construction \
    S3_ACCESS_KEY=x S3_SECRET_KEY=x S3_BUCKET=x S3_ENDPOINT_URL=http://localhost \
    python manage.py collectstatic --noinput -v 0
# Code en lecture seule pour le compte d'exécution (propriété de root).
USER solugation

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8000/api/sante/', headers={'Host': os.environ.get('SOLUGATION_DOMAINE') or 'localhost'}), timeout=4)"
CMD ["sh", "demarrer.sh", "web"]
