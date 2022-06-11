LOCAL_DIR=$(shell pwd)
DOCKER_REPO=zhiyuanyaoj
PROJECT=aquarius
DOCKER_IMAGE=${DOCKER_REPO}/${PROJECT}:latest
WORK_DIR=/opt/aquarius

.PHONY: build-docker, build-origin, run

build-docker:
	docker build \
		-t ${DOCKER_IMAGE} \
		-f build/Dockerfile \
		.

build-origin:
	docker pull ${DOCKER_REPO}/${PROJECT}:base;
	docker pull ${DOCKER_REPO}/${PROJECT}:img;
	docker run -it --name ${PROJECT}-img -d ${DOCKER_REPO}/${PROJECT}:img /bin/bash;
	docker cp ${PROJECT}-img:/opt/img/origin.img data/img/origin.img;
	docker stop ${PROJECT}-img; docker rm ${PROJECT}-img;
	docker build --no-cache \
		-t ${DOCKER_IMAGE} \
		-f build/Dockerfile \
		.

run: ## Run container
	sudo docker run -it \
		--name $(PROJECT) \
		-p 8888:8888 \
		--privileged \
		--cap-add=ALL -d \
		-v $(LOCAL_DIR):$(WORK_DIR) \
		-v /dev:/dev \
		-v /sys/bus:/sys/bus \
		${DOCKER_IMAGE} \
		jupyter notebook --no-browser $(WORK_DIR) --allow-root --ip 0.0.0.0

docker-run-unittest:
	python3 src/test/test_pipeline.py;
	/usr/bin/reset

docker-clean:
	python3 src/test/test_shut_all.py
	rm -rf data/results/unittest;

clean: stop
	docker rmi ${DOCKER_REPO}/${PROJECT}:img;
	rm -rf data/results/unittest;

stop: ## Stop and remove a running container
	docker stop $(PROJECT); docker rm $(PROJECT)

publish: repo-login publish-latest ## Publish the `latest` tagged containers
	
publish-latest: tag-latest ## Publish the `latest` taged container to ECR
	@echo 'publish latest to $(DOCKER_REPO)'
	docker push $(DOCKER_REPO)/$(PROJECT):latest

tag-latest: ## Generate container tag
	@echo 'create tag latest'
	docker tag $(PROJECT) $(DOCKER_REPO)/$(PROJECT):latest

repo-login: ## Auto login to AWS-ECR unsing aws-cli
	@echo 'login docker repo'
	docker login