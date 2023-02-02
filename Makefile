USER_ID := $(shell id -u)
GROUP_ID := ${shell id -g}
COMPOSE_COMMAND = docker-compose
ifeq (, $(shell which docker-compose))
COMPOSE_COMMAND = docker compose
endif


.env:
	cp .env.example .env
	echo "HAL_UID=$(USER_ID)" >> .env
	echo "HAL_GID=$(GROUP_ID)" >> .env
	mkdir -p venv cache.json

hal.env:
	cp hal.env.example hal.env

build: .env
	DOCKER_BUILDKIT=1 $(COMPOSE_COMMAND) build

up: .env
	DOCKER_BUILDKIT=1 $(COMPOSE_COMMAND) up -d api

down:
	DOCKER_BUILDKIT=1 $(COMPOSE_COMMAND) down
