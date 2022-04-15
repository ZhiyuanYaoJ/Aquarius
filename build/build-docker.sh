#!/bin/bash

PROJECT=aquarius
DOCKER_IMAGE=${PROJECT}:latest
BASE_DOCKER_IMAGE=${PROJECT}:base

docker pull zhiyuanyaoj/research:latest
docker build --no-cache \
	-t $PROJECT \
	-f build/Dockerfile \
	.
