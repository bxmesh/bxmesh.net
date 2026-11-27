# bxmesh.net: static files. The only build step writes the links from site.env
# into the pages, and fails if any @PLACEHOLDER@ is left unfilled.
FROM alpine:3.24.4@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf AS build
COPY public /site
COPY site.env /site.env
RUN set -a && . /site.env && set +a \
 && LOCAL_DISCORD_LABEL="${LOCAL_DISCORD#https://}" \
 && find /site -name '*.html' -exec sed -i \
      -e "s|@LOCAL_DISCORD_LABEL@|${LOCAL_DISCORD_LABEL}|g" \
      -e "s|@LOCAL_DISCORD@|${LOCAL_DISCORD}|g" {} + \
 && ! grep -rn '@[A-Z_]*@' /site --include='*.html'

# NGINX's own unprivileged build of the official image: it runs as uid 101 and
# listens on 8080, as the dmz zone's Pod Security (restricted) requires.
FROM nginxinc/nginx-unprivileged:1.31.7-alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e
COPY --from=build /site /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
