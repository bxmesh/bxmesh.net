# bxmesh.net/repeaters/: the backbone list, fetched from CoreScope in the background (backbone.py).
# The observers image's own base; the standard library only.
FROM python:3.13.18-slim-trixie@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50
WORKDIR /app
COPY backbone.py .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# nginx's user (uid 101): it runs in the site pod, which the chart runs as 101 throughout.
USER 101:101
CMD ["python", "/app/backbone.py"]
