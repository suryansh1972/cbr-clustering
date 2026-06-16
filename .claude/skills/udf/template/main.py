"""Custom node template.

Contract:
- Reads NODE_CONTEXT (JSON env var) for node identity, inputs, outputs, config.
- Reads S3_* env vars for MinIO/S3 access (temporary STS credentials).
- Downloads inputs from inputs[i].output.path, writes outputs to the EXACT
  paths in output.files[i].path.
- Prints a final JSON status to stdout; exits 0 on success, 1 on failure.
"""

import json
import os
import shutil
import sys
import tempfile

import boto3

NODE_PREFIX = "[MY NODE]"


def log(message: str) -> None:
    print(f"{NODE_PREFIX} {message}", flush=True)


def log_error(message: str) -> None:
    print(f"{NODE_PREFIX} ERROR: {message}", file=sys.stderr, flush=True)


def make_s3_client():
    endpoint = os.environ.get("S3_ENDPOINT", "minio:9000")
    use_ssl = os.environ.get("S3_USE_SSL", "false").lower() == "true"
    if "://" not in endpoint:
        endpoint = ("https://" if use_ssl else "http://") + endpoint
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        aws_session_token=os.environ.get("S3_SESSION_TOKEN") or None,
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    )


def split_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got: {uri}")
    bucket, _, key = uri[len("s3://"):].partition("/")
    return bucket, key


def main() -> None:
    ctx = json.loads(os.environ["NODE_CONTEXT"])
    node_name = ctx["node"]["name"]
    config = ctx.get("config", {})
    inputs = ctx.get("inputs", [])
    out_files = ctx["output"]["files"]

    log(f"Starting node '{node_name}' with {len(inputs)} input(s)")
    s3 = make_s3_client()
    workdir = tempfile.mkdtemp(prefix="my_node_")
    try:
        # 1. Download inputs
        local_inputs = []
        for inp in inputs:
            bucket, key = split_s3_uri(inp["output"]["path"])
            local_path = os.path.join(workdir, os.path.basename(key))
            log(f"Downloading s3://{bucket}/{key}")
            s3.download_file(bucket, key, local_path)
            local_inputs.append(local_path)

        # 2. Process — replace with real logic, using `config` values as needed
        result_path = os.path.join(workdir, "result.parquet")
        raise NotImplementedError("Implement processing here")

        # 3. Upload outputs to the exact paths the platform expects
        outputs = []
        for out in out_files:
            bucket, key = split_s3_uri(out["path"])
            log(f"Uploading result to s3://{bucket}/{key}")
            s3.upload_file(result_path, bucket, key)
            outputs.append({"name": out.get("name"), "path": out["path"]})

        print(json.dumps({"success": True, "nodeName": node_name, "outputs": outputs}))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # final status must reach stdout, exit code must signal failure
        log_error(str(exc))
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)
