# bxmesh.net

The website, and the observer sign-up, approvals and email as a second image on its own paths,
`/join` and `/admin` (behind Access). The design, the layout and the rules are in
[`zindello-cluster/cluster-docs`](https://github.com/zindello-cluster/cluster-docs).

| Path | What it is |
| --- | --- |
| `site/` | The static site (nginx): its pages, styles and fonts. Image `ghcr.io/bxmesh/bxmesh.net/site` |
| `backbone/` | The backbone list on `/repeaters/`: beside nginx in each site pod, it reads CoreScope's public API every 10 minutes and writes the region's top eight repeaters, by the packets each relayed over the last day (shown per hour), as HTML that nginx includes into the page. Image `ghcr.io/bxmesh/bxmesh.net/backbone` |
| `observers/` | The observer sign-up (`/join`), approvals (`/admin`, behind Cloudflare Access) and email (Flask). Image `ghcr.io/bxmesh/bxmesh.net/observers` |
| `deploy/` | The chart Argo CD deploys: bxmesh.net into `dmz-bxmesh` from `main`, the dev site into `dmz-bxmesh-dev` from `dev` (`values-dev.yaml`), and the previews into `dmz-bxmesh-preview` (`values-preview.yaml`), each on merge (O282) |
| `.github/workflows/build.yml` | On each pull request into `dev` or `main`, and each push to them: the tests (`observers/tests`, `backbone/test_backbone.py`, and the site image's `nginx -t` and `site/check.py`). On a pull request, once they pass: builds the images it changes, pushes them tagged with the commit SHA, and writes the tags into `deploy/values.yaml` on the pull request's branch. `dev` into `main` builds nothing: it carries dev's images |

## Making a change (O282)

1. Branch from `dev`, the default branch, and open a pull request into `dev`.
2. For a preview, label the pull request `preview`: it's deployed at `pr-<number>.bxmesh.net`
   within a few minutes of its image being built, and updated with each push. Removing the label
   or closing the pull request takes it down.
3. Merging into `dev` releases [dev.bxmesh.net](https://dev.bxmesh.net).
4. When everyone is happy, merge `dev` into `main`: that releases bxmesh.net.

The dev site and the previews are the website only (no `/join` or `/admin`), and not indexed.

The gateway sends bxmesh.net's `/join` and `/admin` to the observers app and everything else to
the site. Approving an application creates the observer's login on the broker through EMQX's API,
in `corescope.bxmesh.net`'s namespace (O127).

The Repeaters page's list is CoreScope's, not hand-picked. The page carries a fallback list,
which it shows until the backbone container's first fetch, or if CoreScope can't be reached
before then; after that a failed fetch keeps the last list. All links off bxmesh.net open in a
new tab.
