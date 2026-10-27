# observers.bxmesh.net: apply for an MQTT login; approvals at /admin.
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates templates
ENV PYTHONUNBUFFERED=1
# One worker: the app runs one background poller and writes one SQLite file.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
