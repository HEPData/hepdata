#!/bin/bash -e

TAG="${CI_TAG:-$(git describe --always --tags)}"

retry() {
    "${@}" || "${@}" || exit 2
}

login() {
  echo "Logging into Docker Hub"
  retry docker login \
      "--username=${DOCKERHUB_USER}" \
      "--password=${DOCKERHUB_TOKEN}"
}

buildPush() {
  context="${1}"
  image="${2}"
  echo "Building docker image for ${context}"
  retry docker pull "${image}"
  if docker pull "${image}:build-stage"; then
    retry docker build \
    --build-arg VERSION="${TAG}" \
    -t "${image}:build-stage" \
    "${context}" \
    --cache-from "${image}:build-stage" \
    --target "build-stage"
    retry docker push "${image}:build-stage"
    retry docker build \
      --build-arg VERSION="${TAG}" \
      -t "${image}:${TAG}" \
      -t "${image}" \
      "${context}" \
      --cache-from "${image}:build-stage" \
      --cache-from "${image}"
  else
    retry docker build \
      --build-arg VERSION="${TAG}" \
      -t "${image}:${TAG}" \
      -t "${image}" \
      "${context}" \
      --cache-from "${image}"
  fi

  echo "Pushing image to ${image}:${TAG}"
  retry docker push "${image}:${TAG}"
  retry docker push "${image}"
}

logout() {
  echo "Logging out""${@}"
  retry docker logout
}

deployQA() {
  app="${1}"
  if [ -z "${CI_TAG}" ]; then
    echo "Deploying ${app} ..."
    curl -X POST \
      -F token=${DEPLOY_QA_TOKEN} \
      -F ref=master \
      -F variables[APP_NAME]=${app} \
      -F variables[NEW_TAG]=${TAG} \
      https://gitlab.cern.ch/api/v4/projects/11111/trigger/pipeline
  fi
}

main() {
  login
  buildPush "." "hepdata/hepdata"
  logout
  # FIXME: Enable when cluster is ready
  # deployQA "hepdata"
}
main
