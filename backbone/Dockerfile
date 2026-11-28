# bxmesh.net/repeaters/: the backbone list, fetched from CoreScope in the background (backbone.py).
# The observers image's own base; the standard library only.
FROM python:3.13.18-slim-trixie@sha256:168d3a5d10f2152f8e8d77b6843ac82c22a846cfefeef7afdf9aa630404e82a7
WORKDIR /app
COPY backbone.py .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# nginx's user (uid 101): it runs in the site pod, which the chart runs as 101 throughout.
USER 101:101
CMD ["python", "/app/backbone.py"]
