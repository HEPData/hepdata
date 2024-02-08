#!/bin/bash -e

IMAGE="hepdata/hepdata"
TAG="${CI_TAG:-$(git describe --always --tags)}"

retry() {
    "${@}" || "${@}" || exit 2
}

echo "Logging into Docker Hub"
retry docker login \
    "--username=${DOCKERHUB_USER}" \
    "--password=${DOCKERHUB_TOKEN}"

echo "Building ${IMAGE}"
retry docker build \
  --target "build" \
  --build-arg VERSION="${TAG}" \
  -t "${IMAGE}:${TAG}" \
  -t "${IMAGE}" \
  .

echo "Building ${IMAGE}-statics"
retry docker build \
  --target "statics" \
  --build-arg VERSION="${TAG}" \
  -t "${IMAGE}-statics:${TAG}" \
  -t "${IMAGE}-statics" \
  .

echo "Pushing ${IMAGE}"
retry docker push "${IMAGE}:${TAG}"
retry docker push "${IMAGE}"

echo "Pushing ${IMAGE}-statics"
retry docker push "${IMAGE}-statics:${TAG}"
retry docker push "${IMAGE}-statics"

echo "Logging out""${@}"
retry docker logout
