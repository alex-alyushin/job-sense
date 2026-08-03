include .env
export

# DOCKER

network:
	docker network inspect aggregator-net >/dev/null 2>&1 || \
	docker network create aggregator-net

postgres: network
	@if docker inspect aggregator-pg >/dev/null 2>&1; then \
		docker start aggregator-pg 2>/dev/null || true; \
	else \
		docker run -d \
			--name aggregator-pg \
			--network aggregator-net \
			-e POSTGRES_DB=$(POSTGRES_DB) \
			-e POSTGRES_USER=$(POSTGRES_USER) \
			-e POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) \
			-p 5432:5432 \
			-v aggregator_data:/var/lib/postgresql/data \
			pgvector/pgvector:pg17; \
	fi

dashboard: network
	@if docker inspect aggregator-dashboard >/dev/null 2>&1; then \
		docker start aggregator-dashboard 2>/dev/null || true; \
	else \
		docker run -d \
			--name aggregator-dashboard \
			--network aggregator-net \
			-p 3030:3000 \
			-v grafana_data:/var/lib/grafana \
			grafana/grafana; \
	fi


# SERVICES

telegram:
	uv run python -m gateways.telegram

llm:
	uv run python -m llm_service.main

search:
	uv run python -m search_service.main

report:
	uv run python -m report_service.main

up: postgres dashboard
	@trap 'kill 0' INT TERM EXIT; \
	uv run python -m gateways.telegram   2>&1 | sed $$'s/^/\033[34m/; s/$$/\033[0m/' & \
	uv run python -m llm_service.main    2>&1 | sed $$'s/^/\033[35m/; s/$$/\033[0m/' & \
	uv run python -m search_service.main 2>&1 | sed $$'s/^/\033[36m/; s/$$/\033[0m/' & \
	uv run python -m report_service.main 2>&1 | sed $$'s/^/\033[32m/; s/$$/\033[0m/' & \
	wait


# DATABASE

db_drop:
	uv run python -m database.db_drop

db_init:
	uv run python -m database.db_init

db: postgres \
	db_drop \
	db_init
