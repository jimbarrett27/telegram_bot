"""One-off: create the public-read GCS bucket the tapestry is served from.

Run once (needs GCP credentials with storage admin on the project):

    uv run python -m tapestry.setup_bucket

Idempotent: skips creation if the bucket already exists, and only applies the
public-read IAM binding if it isn't already present.
"""

import logging

from google.cloud import storage

from tapestry.storage import BUCKET_NAME, PROJECT_ID

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

LOCATION = "EU"
PUBLIC_ROLE = "roles/storage.objectViewer"

# The website fetches index.json / panels/*.json from the browser via XHR, which
# is CORS-gated even though the objects are public-read. Allow cross-origin GETs.
CORS_RULE = {
    "origin": ["*"],
    "method": ["GET"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600,
}


def main() -> None:
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    if bucket.exists():
        print(f"Bucket gs://{BUCKET_NAME} already exists")
    else:
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        client.create_bucket(bucket, location=LOCATION)
        print(f"Created gs://{BUCKET_NAME} in {LOCATION}")

    policy = bucket.get_iam_policy(requested_policy_version=3)
    already_public = any(
        b["role"] == PUBLIC_ROLE and "allUsers" in b["members"] for b in policy.bindings
    )
    if already_public:
        print("Public read already granted")
    else:
        policy.bindings.append({"role": PUBLIC_ROLE, "members": {"allUsers"}})
        bucket.set_iam_policy(policy)
        print("Granted allUsers objectViewer (public read)")

    if bucket.cors == [CORS_RULE]:
        print("CORS already configured")
    else:
        bucket.cors = [CORS_RULE]
        bucket.patch()
        print("Configured CORS (GET from any origin)")


if __name__ == "__main__":
    main()
