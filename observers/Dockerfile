# bxmesh.net/join and /admin: apply for an MQTT login; approvals at /admin.
FROM python:3.13.18-slim-trixie@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py gunicorn.conf.py ./
COPY templates templates
ENV PYTHONUNBUFFERED=1
# Not root: the dmz zone's Pod Security is restricted. A numeric user, so the
# kubelet can check it; the chart sets the same uid and gives its volume and
# secrets to its group (fsGroup).
USER 10001:10001
# One worker: the app runs one background poller and writes one SQLite file.
# gunicorn.conf.py: the access log without the email links' tokens.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
