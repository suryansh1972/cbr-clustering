# Runtime Contract (what the container receives)

## Environment variables

The pod receives exactly these environment variables:

| Var | Content |
|---|---|
| `NODE_CONTEXT` | JSON string with node identity, inputs, outputs, and config (see below) |
| `S3_ENDPOINT` | MinIO endpoint, host:port, **no scheme** (in-cluster: `minio.data-pipeline.svc.cluster.local:9002`) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Temporary STS credentials scoped to the user's prefix (lifetime ≈ `STS_SESSION_DURATION_IN_SECONDS`, default 900s) |
| `S3_SESSION_TOKEN` | STS session token — may be absent or empty; handle conditionally |
| `S3_BUCKET` | Data bucket (`data-pipeline`) |
| `S3_USE_SSL` | `"true"` / `"false"` |
| `S3_REGION` | e.g. `us-east-1` |

## NODE_CONTEXT structure

```json
{
  "node": {
    "name": "my_sql_transform",     // user-entered config.name
    "slug": "sql-transformer"       // node type slug
  },
  "inputs": [
    {
      "nodeSlug": "csv-source",     // upstream node TYPE slug
      "nodeName": "source_data",    // upstream node's user-entered name
      "output": {
        "name": "result",           // upstream outputFiles[].name
        "path": "s3://data-pipeline/<user>/artifacts/.../result.parquet",
        "format": "parquet"
      }
    }
  ],
  "output": {
    "basePath": "s3://data-pipeline/<user>/artifacts/<pipeline>/<exec>/<node-name>",
    "files": [
      { "name": "result", "path": "s3://.../result.parquet", "format": "parquet" }
    ]
  },
  "config": {                       // all user config values as entered
    "sql": "SELECT * FROM input_data"
  }
}
```

## Container obligations

1. Parse `NODE_CONTEXT`; fail fast (exit 1) if missing.
2. Read inputs from `inputs[i].output.path` (S3 URIs).
3. Write each output to the **exact** path in `output.files[i].path` — downstream nodes are told that path.
4. Print a final JSON status to stdout, e.g. `{"success": true, "nodeName": "...", "outputs": [...]}` (on error: `{"success": false, "error": "..."}`). This is observability-only — the platform never parses it.
5. Exit 0 on success, non-zero on failure — the exit code is the **only** signal the platform uses to mark the step completed/failed.
6. Log diagnostics to stdout/stderr with a prefix (e.g. `[MY NODE]`) and flush — logs are archived and shown in the platform UI.

Pod resources (defaults from backend env): requests 256Mi / 100m, limits 2Gi / 2 CPU.

## Python skeleton

```python
import json, os, sys

def log(msg): print(f"[MY NODE] {msg}", flush=True)

def main():
    ctx = json.loads(os.environ["NODE_CONTEXT"])
    node_name = ctx["node"]["name"]
    config = ctx.get("config", {})
    inputs = ctx.get("inputs", [])
    out_files = ctx["output"]["files"]

    # --- S3 client (boto3 variant) ---
    import boto3
    endpoint = os.environ.get("S3_ENDPOINT", "minio:9000")
    use_ssl = os.environ.get("S3_USE_SSL", "false").lower() == "true"
    if "://" not in endpoint:
        endpoint = ("https://" if use_ssl else "http://") + endpoint
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        aws_session_token=os.environ.get("S3_SESSION_TOKEN") or None,
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    )

    def split_s3(uri):  # "s3://bucket/key" -> (bucket, key)
        rest = uri[len("s3://"):]
        bucket, _, key = rest.partition("/")
        return bucket, key

    # download inputs, process, upload to out_files[i]["path"] ...

    print(json.dumps({"success": True, "nodeName": node_name,
                      "outputs": [{"name": f["name"], "path": f["path"]} for f in out_files]}))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[MY NODE ERROR] {e}", file=sys.stderr, flush=True)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
```

## DuckDB variant (tabular data)

For SQL-over-parquet nodes:

```python
import duckdb
conn = duckdb.connect(":memory:")
conn.install_extension("httpfs"); conn.load_extension("httpfs")
session = os.environ.get("S3_SESSION_TOKEN", "")
conn.execute(f"""
    CREATE SECRET s3_secret (
        TYPE S3,
        KEY_ID '{os.environ["S3_ACCESS_KEY"]}',
        SECRET '{os.environ["S3_SECRET_KEY"]}',
        ENDPOINT '{os.environ["S3_ENDPOINT"]}',
        URL_STYLE 'path',
        USE_SSL {os.environ.get("S3_USE_SSL", "false").lower()},
        REGION '{os.environ.get("S3_REGION", "us-east-1")}'
        {f", SESSION_TOKEN '{session}'" if session else ""}
    )
""")
# load each input as a table named after the upstream node:
# sanitize: re.sub(r'[^a-zA-Z0-9_]', '_', input["nodeName"])
# CREATE TABLE {tbl} AS SELECT * FROM read_parquet('{input["output"]["path"]}')
# if exactly one input, also: CREATE VIEW input_data AS SELECT * FROM {tbl}
# write: COPY result TO '{path}' (FORMAT PARQUET, COMPRESSION 'snappy')
```

Convention: expose each upstream table by the upstream node's (sanitized) name, plus an `input_data` alias when there is exactly one input. Reuse this convention for consistency with other SQL nodes.
