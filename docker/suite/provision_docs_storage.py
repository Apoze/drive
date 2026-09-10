"""Initialize the dedicated Docs bucket and verify versioned S3 behavior."""

import argparse
import json
from pathlib import Path
import subprocess


PROVISION = """
import boto3
from uuid import uuid4
from botocore.exceptions import ClientError

s3 = config["s3"]
def client(credentials):
    return boto3.client("s3", endpoint_url=s3["endpoint"], region_name="us-east-1",
                        aws_access_key_id=credentials["access_key"],
                        aws_secret_access_key=credentials["secret_key"])
admin, app = client(config["s3_admin"]), client(s3)
bucket = s3["bucket"]
try:
    admin.head_bucket(Bucket=bucket)
except ClientError as error:
    if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
        raise
    admin.create_bucket(Bucket=bucket)
if admin.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
    admin.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
key = "suite-storage-check/" + str(uuid4())
versions = []
try:
    first = app.put_object(Bucket=bucket, Key=key, Body=b"suite-storage-check",
                           Metadata={"status": "processing"}, ContentType="text/plain")
    versions.append(first["VersionId"])
    second = app.copy_object(Bucket=bucket, Key=key, CopySource={"Bucket": bucket, "Key": key},
                              Metadata={"status": "ready"}, MetadataDirective="REPLACE",
                              ContentType="text/plain")
    versions.append(second["VersionId"])
    assert len(set(versions)) == 2, "Metadata replacement must create a new version"
    for version in versions:
        response = app.get_object(Bucket=bucket, Key=key, VersionId=version)
        with response["Body"] as body:
            assert body.read(64) == b"suite-storage-check", "Version content differs"
    assert app.head_object(Bucket=bucket, Key=key)["Metadata"]["status"] == "ready"
finally:
    # Only this invocation's unpredictable synthetic key is removed.
    for page in app.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=key):
        for version in page.get("Versions", []) + page.get("DeleteMarkers", []):
            if version["Key"] == key:
                app.delete_object(Bucket=bucket, Key=key, VersionId=version["VersionId"])
print("Docs S3: bucket ready, versioned metadata copy and reads verified; probe removed.")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--container", default="suite-local-docs-1")
    args = parser.parse_args()
    config = json.loads((args.state / "settings.json").read_text())
    private = {key: config[key] for key in ("s3", "s3_admin")}
    # Credentials travel through stdin, never the process arguments or console.
    result = subprocess.run(
        ["docker", "exec", "-i", args.container, "python", "-"],
        input="config = " + repr(private) + "\n" + PROVISION,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        # SDK tracebacks can contain request metadata; report a sanitized failure.
        raise SystemExit(
            "Docs S3 provisioning failed; inspect the private installation configuration."
        )
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
