# bxmesh.net: static files. The only build step writes the links from site.env
# into the pages, and fails if any @PLACEHOLDER@ is left unfilled.
FROM alpine:3 AS build
COPY public /site
COPY site.env /site.env
RUN set -a && . /site.env && set +a \
 && LOCAL_DISCORD_LABEL="${LOCAL_DISCORD#https://}" \
 && find /site -name '*.html' -exec sed -i \
      -e "s|@LOCAL_DISCORD_LABEL@|${LOCAL_DISCORD_LABEL}|g" \
      -e "s|@LOCAL_DISCORD@|${LOCAL_DISCORD}|g" {} + \
 && ! grep -rn '@[A-Z_]*@' /site --include='*.html'

FROM nginx:alpine
COPY --from=build /site /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
