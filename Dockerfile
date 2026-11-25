FROM python:3.12-slim

RUN useradd --create-home --uid 10001 helpdesk && mkdir -p /dados /data && chown -R helpdesk:helpdesk /dados /data
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY services ./services
COPY gateway ./gateway

USER helpdesk
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
