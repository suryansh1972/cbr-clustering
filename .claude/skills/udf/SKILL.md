---
name: udf
description: Create a UDF (user-defined function — a custom node) for the no-code pipeline editor — author node.json, the container script, and Dockerfile, then register and build it. Use when asked to create, scaffold, modify, or debug a UDF, custom node, or pipeline node.
---

# Creating a UDF (User-Defined Function)

A UDF — called a "custom node" throughout the platform's code and UI — is a containerized step in the visual pipeline builder. It lives in its own **public GitHub repo** containing a `node.json` contract, a script, and a Dockerfile. The platform builds the image from that repo, pushes it to its registry, and runs it as a pod when a pipeline executes.

A starter template is in this skill's `template/` directory (boto3 download → process → upload). A DuckDB variant for SQL-over-parquet nodes is in `references/runtime-contract.md`.

## Core contract

- Runtime input is a **single `NODE_CONTEXT` JSON env var** plus `S3_*` credentials — nothing else is injected by the platform.
- `node.json` is validated server-side by a **strict** schema — unknown fields are **rejected**.

## Steps

### 1. Scaffold the node directory

```
my-node/
  node.json          # contract (see references/node-json.md for full schema)
  main.py            # entrypoint script
  Dockerfile
  requirements.txt
```

Copy `template/` from this skill as a starting point. Minimum viable `node.json` for a processing node:

```json
{
  "version": "1.0",
  "nodeType": "processing",
  "name": "My Node",
  "shortDescription": "One line, max 200 chars",
  "description": "Longer description",
  "hasInput": true,
  "inputDescription": "What inputs this accepts",
  "config": {
    "name": {
      "type": "string",
      "label": "Name",
      "description": "Unique identifier for this node in the pipeline",
      "required": true,
      "unique": true,
      "placeholder": "e.g. my_step",
      "validation": { "patternKey": "snake_case" }
    }
  },
  "hasOutput": true,
  "outputDescription": "What this produces",
  "outputFiles": [
    {
      "name": "result",
      "path": "{{artifacts}}/{{pipeline.name}}/{{execution.timestamp}}/{{node.name}}/result.parquet"
    }
  ],
  "implementation": {
    "type": "container",
    "entrypoint": "python main.py",
    "dockerfilePath": "Dockerfile",
    "dockerContext": "."
  }
}
```

Hard rules (enforced at registration):
- `config.name` is **mandatory** with `type: "string"`, `required: true`, `unique: true` (label must be "Name"). Only `description`, `placeholder`, and `validation.patternKey` are customizable.
- `nodeType: "config"` nodes must NOT have `implementation`; processing nodes need it to run a container.
- If `hasInput: false`, `inputDescription` must be empty; if `hasOutput: false`, `outputDescription` and `outputFiles` must be empty.
- Output file `name`s must be unique within `outputFiles`.
- No custom regex in validation — only predefined `patternKey` values (ReDoS protection).
- `entrypoint` command must be on the allowlist (`python`, `python3`, `node`, `java`, `bash`, `sh`, or their `/usr/bin`//`/bin` paths) with no shell metacharacters.

Full field reference: `references/node-json.md`.

### 2. Write the script

The container receives everything through env vars — read `NODE_CONTEXT` (JSON), download inputs from S3/MinIO, process, upload outputs to the exact paths in `output.files[].path`, print a JSON status line to stdout, exit 0 on success / 1 on failure.

Full runtime contract + Python skeleton: `references/runtime-contract.md`.

### 3. Write the Dockerfile

Convention:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt main.py ./
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]
```

- `CMD` should match `implementation.entrypoint`.
- Pre-install anything that downloads at runtime (e.g. the DuckDB httpfs extension: `RUN python -c "import duckdb; duckdb.connect().install_extension('httpfs')"`) — pods may have restricted/slow network.
- Build must finish within `NODE_BUILD_TIMEOUT_SECONDS` (default 1800s).

### 4. Push to a public GitHub repo

The build workflow clones without credentials, so the repo must be public and on `github.com` (the contract's `githubUrl` validator rejects other hosts and embedded credentials). Multiple nodes can share one repo — set `implementation.dockerContext` to the node's subdirectory (e.g. `"dockerContext": "sql-transformer"`).

### 5. Register and build

In the platform web UI: **Node Management → onboard node** — enter the GitHub URL/ref, paste or build the contract, pick the icon (`lucideIcon`) and `color`, save, then trigger the build and watch its status/logs on the node's page.

Notes:
- Node `name` is **globally unique, including soft-deleted nodes** — deleted names stay reserved.
- New nodes start as `visibility: "draft"` and can be flipped to `"publish"`. Visibility is stored/displayed but does not currently filter listings — non-admin users see only their **own** nodes either way. The palette additionally requires a **completed build**. Creating a node does NOT auto-trigger a build — it's a separate step.
- The image is built and pushed to the platform registry as `custom-node-{slug}` (slug auto-generated from name, kebab-case, ≤40 chars).

Build system details and debugging: `references/build-and-register.md`.

### 6. Test end-to-end

1. Drag the node onto a canvas, set config (the node name must match `^[a-zA-Z_][a-zA-Z0-9_]*$`, ≤80 chars, unique in pipeline — enforced at execute time).
2. Run the pipeline; open the execution view and read the node's logs there.
3. Verify the output landed at the expected S3 path in the `data-pipeline` bucket.

## Common pitfalls

- Reading `INPUTS`/`OUTPUTS`/`CONFIG` env vars — they don't exist; only `NODE_CONTEXT` is injected.
- Adding `actions`, `connections`, `category`, or an `outputs` object to node.json — strict schema rejects them.
- `S3_ENDPOINT` has no scheme — prepend `http://`/`https://` based on `S3_USE_SSL` for boto3; for DuckDB use `ENDPOINT` + `URL_STYLE 'path'`.
- `S3_SESSION_TOKEN` may be absent/empty — include it conditionally.
- S3 credentials are short-lived STS tokens (default ~15 min) — long-running nodes can lose access mid-run.
- Upstream inputs arrive as whatever format the upstream wrote (check `inputs[i].output.path` extension/`format`); a SQL-over-parquet node only reads parquet.
- Default pod resources: requests 256Mi/100m, limits 2Gi/2 CPU — size your processing accordingly.
