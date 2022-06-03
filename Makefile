LOCAL_DIR=$(shell pwd)
DOCKER_REPO=zhiyuanyaoj
PROJECT=aquarius-sc22
DOCKER_IMAGE=${DOCKER_REPO}/${PROJECT}:latest

.PHONY: build build-origin

build:
	docker pull ${DOCKER_REPO}/${PROJECT}:latest

build-origin:
	docker pull ${DOCKER_REPO}/research:latest; \
	docker build --no-cache \
		-t ${DOCKER_IMAGE} \
		-f build/Dockerfile \
		.
	
run: ## Run container
	sudo docker run -it --rm -p 8888:8888 -v $(LOCAL_DIR):/opt/aquarius --name $(PROJECT) zhiyuanyaoj/aquarius-sc22:latest jupyter notebook --no-browser /opt/aquarius --allow-root --ip 0.0.0.0

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