# Registration, Builds & Debugging

## Registration & lifecycle

Register in the platform web UI: **Node Management → onboard node**. The contract is validated on save; build logs and status are shown on the node's page.

- Node `name`s are globally unique **including soft-deleted nodes** — deleted names stay reserved. A slug is auto-generated from the name.
- Creating a node does **not** trigger a build — it's a separate step on the node's page.
- Build status: `pending → building → completed/failed`; logs are viewable in the UI. Pending/building builds can be cancelled.
- Visibility is `draft` or `publish` (owner or admin can change it). It is stored/displayed but does not currently filter listings — non-admin users see only their own nodes either way.
- The node appears in the pipeline palette only after a **completed build**.
- Deleting is a soft delete: the name stays reserved, and existing pipelines using the node keep working from the cached contract.

## How builds work

1. The platform clones the GitHub repo **without credentials** (clone timeout ~120s) — the repo must be public and `githubRef` (branch/tag/commit) must exist.
2. The image is built with Buildah using the contract's `dockerfilePath`/`dockerContext`, both relative to the repo root. The whole build must finish within the platform's build timeout (default 1800s).
3. The image is pushed to the platform registry as `custom-node-{slug}` (slug: lowercased, non-alphanumerics → `-`, collapsed, ≤40 chars) and pulled when a pipeline runs the node.

## Test the container locally

You can exercise the full runtime contract without the platform — point the `S3_*` vars at any S3-compatible endpoint (e.g. a local MinIO: `docker run -p 9000:9000 minio/minio server /data`):

```bash
docker build -t my-node:dev .

docker run --rm \
  -e NODE_CONTEXT='{"node":{"name":"test","slug":"my-node"},"inputs":[],"output":{"basePath":"s3://data-pipeline/test","files":[{"name":"result","path":"s3://data-pipeline/test/result.parquet","format":"parquet"}]},"config":{}}' \
  -e S3_ENDPOINT=host.docker.internal:9000 -e S3_ACCESS_KEY=... -e S3_SECRET_KEY=... \
  -e S3_BUCKET=data-pipeline -e S3_USE_SSL=false -e S3_REGION=us-east-1 \
  my-node:dev
```

Check: exit code 0, a final JSON status line on stdout, and the output object written to the exact path in `output.files[0].path`.

## Common build failures

- Repo not public, or `githubRef` doesn't exist.
- `dockerfilePath`/`dockerContext` wrong relative to the repo root (watch this when several nodes share one repo).
- Build exceeding the timeout — slim the base image, pin dependencies, avoid downloading large assets at build time.
