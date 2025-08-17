#!/bin/bash

set -eu

cleanup() {
  echo "Cleaning up buildx builder..."
  docker buildx rm eager_beaver
}

trap cleanup EXIT
docker buildx create --name eager_beaver --use
docker buildx build --platform linux/arm64 -t bastler452/bumper --push .
