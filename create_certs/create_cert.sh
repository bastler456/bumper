#!/bin/bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_OUTPUT_DIR="${SCRIPT_DIR}/../certs"
CERT_CREATION_DIR="${SCRIPT_DIR}"

OUTPUT_DIR="${1:-$DEFAULT_OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

echo "Generating CA key..."
openssl genrsa -out "${OUTPUT_DIR}/ca.key" 4096
chmod 600 "${OUTPUT_DIR}/ca.key"

echo "Generating CA CSR..."
openssl req -new -nodes -key "${OUTPUT_DIR}/ca.key" \
  -config "${CERT_CREATION_DIR}/csrconfig_ca.txt" \
  -out "${OUTPUT_DIR}/ca.csr"

echo "Generating CA certificate..."
openssl req -x509 -nodes -in "${OUTPUT_DIR}/ca.csr" \
  -days 1095 -key "${OUTPUT_DIR}/ca.key" \
  -config "${CERT_CREATION_DIR}/certconfig_ca.txt" \
  -extensions req_ext -out "${OUTPUT_DIR}/ca.crt"

echo "Generating bumper key..."
openssl genrsa -out "${OUTPUT_DIR}/bumper.key" 4096
chmod 600 "${OUTPUT_DIR}/bumper.key"

echo "Generating bumper CSR..."
openssl req -new -nodes -key "${OUTPUT_DIR}/bumper.key" \
  -config "${CERT_CREATION_DIR}/csrconfig_bumper.txt" \
  -out "${OUTPUT_DIR}/bumper.csr"

echo "Signing bumper certificate..."
openssl x509 -req -in "${OUTPUT_DIR}/bumper.csr" \
  -days 365 -CA "${OUTPUT_DIR}/ca.crt" \
  -CAkey "${OUTPUT_DIR}/ca.key" \
  -extfile "${CERT_CREATION_DIR}/certconfig_bumper.txt" \
  -extensions req_ext -CAcreateserial \
  -CAserial "${OUTPUT_DIR}/ca.srl" \
  -out "${OUTPUT_DIR}/bumper.crt"

echo "Done. Certificates created in ${OUTPUT_DIR}"