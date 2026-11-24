# bxmesh.net/join and /admin: apply for an MQTT login; approvals at /admin.
FROM python:3.15.2-slim-trixie@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5
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
