# bxmesh.net

BxMesh, the Bathurst MeshCore community site. Plain static HTML and CSS in `public/`,
served by nginx; no build step. The design is the BXMesh canvas
(claude.ai/artifact/UCx5PVe9vDXTKzvGz3CFba) on the BXMesh design system
(claude.ai/artifact/7uZUm21eKWyPJnbiV22AmW); colours in `styles.css` are that
system's tokens, light by default and dark from the system setting.

Links that change live in `site.env`, the one place to edit them: the image
build writes them into every page in place of `@LOCAL_DISCORD@` (and its
`@LOCAL_DISCORD_LABEL@` text) and fails if any `@PLACEHOLDER@` is left. A new
invite is a one-line change to `site.env`, then push.

Fonts are self-hosted (latin subsets of Bricolage Grotesque, Instrument Sans
and Martian Mono, SIL Open Font Licence: `public/fonts/OFL-*.txt`), so the site
makes no third-party requests.

Facts on the page (radio settings, repeater names, links) come from NSW Mesh
and the MeshCore docs; keep radio values exact. Repeater names are their
owners', emoji included.

Deployed as the `bxmesh` DMZ service (`dmz/services.yml`). It starts
`enabled: false` until the design is approved.
