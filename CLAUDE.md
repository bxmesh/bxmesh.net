# CLAUDE.md — bxmesh/bxmesh.net

The bxmesh.net website and the observer sign-up and approvals on its `/join` and `/admin` paths.
Read [`zindello-cluster/cluster-docs`](https://github.com/zindello-cluster/cluster-docs) before
doing anything here: its `CLAUDE.md`, the spec (`spec/design.md`), the binding layout
(`spec/layout.md`) and the rules (`spec/rules.md`). The rules apply here in full: an agent prepares
a pull request and never merges it or syncs in Argo. Branch from `dev`, the default branch, and open
pull requests into `dev`, not `main`; a release is a pull request from `dev` into `main`. This
repo deploys itself on merge: `dev` to dev.bxmesh.net, `main` to bxmesh.net (O282, the one
exception to O14), so merging is releasing.
