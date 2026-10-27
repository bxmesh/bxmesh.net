# bxmesh.net/join and /admin: apply for an MQTT login; approvals at /admin.
FROM python:3.13.18-slim-trixie@sha256:8a7c3cd378e4e6dfa5d0ea4f6ca1a11068c951e3de3146ebc484eadf4b05a2be
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates templates
ENV PYTHONUNBUFFERED=1
# Not root: the dmz zone's Pod Security is restricted. A numeric user, so the
# kubelet can check it; the chart sets the same uid and gives its volume and
# secrets to its group (fsGroup).
USER 10001:10001
# One worker: the app runs one background poller and writes one SQLite file.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
