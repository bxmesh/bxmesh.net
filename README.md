# bxmesh.net

The website, and the observer sign-up, approvals and email as a second image on its own paths,
`/join` and `/admin` (behind Access). The design, the layout and the rules are in
[`zindello-cluster/cluster-docs`](https://github.com/zindello-cluster/cluster-docs).

| Path | What it is |
| --- | --- |
| `site/` | The static site (nginx): its pages, styles and fonts. Image `ghcr.io/bxmesh/bxmesh.net/site` |
| `observers/` | The observer sign-up (`/join`), approvals (`/admin`, behind Cloudflare Access) and email (Flask). Image `ghcr.io/bxmesh/bxmesh.net/observers` |
| `deploy/` | The chart Argo CD deploys into `dmz-bxmesh`, from `main`, when the owner syncs (O14) |
| `.github/workflows/build.yml` | On each pull request: builds the images it changes, pushes them tagged with the commit SHA, and writes the tags into `deploy/values.yaml` on the pull request's branch |

The gateway sends bxmesh.net's `/join` and `/admin` to the observers app and everything else to
the site. Approving an application creates the observer's login on the broker through EMQX's API,
in `corescope.bxmesh.net`'s namespace (O127).
