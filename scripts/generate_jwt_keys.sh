#!/usr/bin/env bash
# Generate an RS256 JWT signing pair for production use.
set -euo pipefail
mkdir -p certs
openssl genpkey -algorithm RSA -out certs/jwt-private.pem -pkeyopt rsa_keygen_bits:3072 2>/dev/null || \
  openssl genrsa -out certs/jwt-private.pem 3072
openssl rsa -in certs/jwt-private.pem -pubout -out certs/jwt-public.pem
echo "Wrote certs/jwt-private.pem and certs/jwt-public.pem"
echo "Set JWT_ALGORITHM=RS256 with these paths in .env"
