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

for stage in "web" "statics"; do
  stage_image="${IMAGE}-${stage}"
  echo "Building stage ${stage_image}"
  retry docker build \
    --target "${stage}" \
    --build-arg VERSION="${TAG}" \
    -t "${stage_image}:${TAG}" \
    -t "${stage_image}" \
    .

  echo "Pushing image ${stage_image}:${TAG}"
  retry docker push "${stage_image}:${TAG}"
  retry docker push "${stage_image}"
done

echo "Logging out""${@}"
retry docker logout
