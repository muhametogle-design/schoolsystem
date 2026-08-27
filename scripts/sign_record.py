#!/usr/bin/env python
"""Reference CLI for a dean to sign an NE-EMIS lock envelope.

Use it to produce the ``signature`` value for ``POST /locks``:

    python scripts/sign_record.py \
      --private-key certs/demo_dean_private.pem \
      --entity-type payroll_entry \
      --entity-id 50f7f2b4-... \
      --campus-id 11111111-... \
      --locked-by 22222222-... \
      --payload '{"teacher_id":"...","pay_period":"2026-08","net":50000}' \
      --output signature.bin
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Make `app` importable when the script is run directly from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.crypto_lock import (
    build_lock_digest,
    load_private_key,
    payload_digest,
    sign_envelope,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--entity-type", required=True)
    parser.add_argument("--entity-id", required=True)
    parser.add_argument("--campus-id", required=True)
    parser.add_argument("--locked-by", required=True)
    parser.add_argument("--payload", required=True, help="JSON payload")
    parser.add_argument("--key-version", type=int, default=1)
    parser.add_argument("--signature-scheme", default="ed25519")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = load_private_key(Path(args.private_key).read_bytes())
    payload = json.loads(args.payload)
    hash_value = payload_digest(payload)
    digest = build_lock_digest(
        args.entity_type,
        uuid.UUID(args.entity_id),
        uuid.UUID(args.campus_id),
        hash_value,
        signature_scheme=args.signature_scheme,
        key_version=args.key_version,
        locked_by=args.locked_by,
    )
    sig = sign_envelope(key, digest)
    Path(args.output).write_bytes(sig)
    print(f"payload_hash={hash_value}")
    print(f"signature_written={args.output}")


if __name__ == "__main__":
    sys.exit(main())
