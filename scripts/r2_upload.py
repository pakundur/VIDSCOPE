#!/usr/bin/env python3
"""Upload the Agensi ZIP to R2 using S3 SigV4 (stdlib only, no boto3).

Reads credentials from ~/.cfenv. Verifies the upload by fetching the object
back and comparing SHA-256 against the local file. A 200 from PUT is not
proof the bytes landed correctly.
"""
import datetime
import hashlib
import hmac
import os
import pathlib
import subprocess
import sys
import urllib.request

# All deployment specifics come from the environment, so this file carries no
# bucket names, account ids or hostnames. Source an env file before running:
#   R2_ACCESS_KEY, R2_SECRET_KEY, R2_ENDPOINT, R2_BUCKET, R2_PUBLIC_BASE
ENV = pathlib.Path(os.environ.get("R2_ENV_FILE", pathlib.Path.home() / ".cfenv"))
ZIP = pathlib.Path(os.environ.get(
    "VS_ZIP", pathlib.Path.home() / "repos/vidscope/dist/agensi/vidscope-agensi.zip"))
KEY = os.environ.get("R2_KEY", "vidscope/vidscope-agensi.zip")
BUCKET = os.environ.get("R2_BUCKET", "")


def load_env():
    """Source ~/.cfenv into this process."""
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not line.startswith("export "):
            continue
        k, _, v = line[len("export "):].partition("=")
        os.environ[k.strip()] = v.strip()


class R2:
    def __init__(self):
        self.ak = os.environ["R2_ACCESS_KEY"]
        self.sk = os.environ["R2_SECRET_KEY"]
        self.ep = os.environ["R2_ENDPOINT"].rstrip("/")
        self.host = self.ep.split("://", 1)[1]

    def _sign(self, method, path, query, payload_hash):
        now = datetime.datetime.now(datetime.timezone.utc)
        amz = now.strftime("%Y%m%dT%H%M%SZ")
        ds = now.strftime("%Y%m%d")
        signed = "host;x-amz-content-sha256;x-amz-date"
        ch = (
            f"{method}\n{path}\n{query}\n"
            f"host:{self.host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz}\n\n"
            f"{signed}\n{payload_hash}"
        )
        scope = f"{ds}/auto/s3/aws4_request"
        sts = (f"AWS4-HMAC-SHA256\n{amz}\n{scope}\n"
               + hashlib.sha256(ch.encode()).hexdigest())

        def h(k, m):
            return hmac.new(k, m.encode(), hashlib.sha256).digest()

        k = h(("AWS4" + self.sk).encode(), ds)
        k = h(k, "auto"); k = h(k, "s3"); k = h(k, "aws4_request")
        sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
        return (f"AWS4-HMAC-SHA256 Credential={self.ak}/{scope}, "
                f"SignedHeaders={signed}, Signature={sig}"), amz

    def put(self, bucket, key, data, content_type):
        ph = hashlib.sha256(data).hexdigest()
        path = f"/{bucket}/{key}"
        auth, amz = self._sign("PUT", path, "", ph)
        req = urllib.request.Request(f"{self.ep}{path}", data=data, method="PUT")
        req.add_header("Authorization", auth)
        req.add_header("x-amz-date", amz)
        req.add_header("x-amz-content-sha256", ph)
        req.add_header("Content-Type", content_type)
        req.add_header("Content-Length", str(len(data)))
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status

    def get(self, bucket, key):
        ph = hashlib.sha256(b"").hexdigest()
        path = f"/{bucket}/{key}"
        auth, amz = self._sign("GET", path, "", ph)
        req = urllib.request.Request(f"{self.ep}{path}", method="GET")
        req.add_header("Authorization", auth)
        req.add_header("x-amz-date", amz)
        req.add_header("x-amz-content-sha256", ph)
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read()


def main():
    load_env()
    data = ZIP.read_bytes()
    local_sha = hashlib.sha256(data).hexdigest()
    print(f"local  : {ZIP.name}  {len(data):,} bytes")
    print(f"sha256 : {local_sha}")

    r2 = R2()
    print(f"\nuploading to s3://{BUCKET}/{KEY} ...")
    status = r2.put(BUCKET, KEY, data, "application/zip")
    print(f"PUT status: {status}")

    print("\nverifying by fetching back ...")
    gstatus, back = r2.get(BUCKET, KEY)
    back_sha = hashlib.sha256(back).hexdigest()
    print(f"GET status: {gstatus}  {len(back):,} bytes")
    print(f"sha256  : {back_sha}")
    print()
    if back_sha == local_sha and len(back) == len(data):
        print("VERIFIED: bytes round-trip identical")
    else:
        print("MISMATCH: upload corrupted")
        return 1

    public_base = os.environ.get("R2_PUBLIC_BASE", "").rstrip("/")
    print(f"\nobject key: s3://{BUCKET}/{KEY}")
    if public_base:
        print("public download URL:")
        print(f"  {public_base}/{KEY}")
        print("\nverify the link serves before sharing it:")
        print(f"  curl -sI {public_base}/{KEY} | head -1")
    else:
        print("R2_PUBLIC_BASE not set; no public URL to report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
