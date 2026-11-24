# bxmesh.net/repeaters/: the backbone list, fetched from CoreScope in the background (backbone.py).
# The observers image's own base; the standard library only.
FROM python:3.15.2-slim-trixie@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5
WORKDIR /app
COPY backbone.py .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# nginx's user (uid 101): it runs in the site pod, which the chart runs as 101 throughout.
USER 101:101
CMD ["python", "/app/backbone.py"]
