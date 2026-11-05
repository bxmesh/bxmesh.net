# bxmesh.net/repeaters/: the backbone list, fetched from CoreScope in the background (backbone.py).
# The observers image's own base; the standard library only.
FROM python:3.13.18-slim-trixie@sha256:8a7c3cd378e4e6dfa5d0ea4f6ca1a11068c951e3de3146ebc484eadf4b05a2be
WORKDIR /app
COPY backbone.py .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# nginx's user (uid 101): it runs in the site pod, which the chart runs as 101 throughout.
USER 101:101
CMD ["python", "/app/backbone.py"]
