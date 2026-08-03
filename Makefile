include .env
export

# run:
# 	uv run python main.py

# brightdata_test_api:
# 	uv run python junk/brightdata_test_api.py

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
			postgres:17; \
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

telegram:
	uv run python -m gateways.telegram_gateway

llm:
	uv run python -m services.llm_service

echo:
	uv run python -m services.echo_service

# search:
# 	uv run python -m services.search_service

up: postgres dashboard
	@trap 'kill 0' INT TERM EXIT; \
	uv run python -m gateways.telegram_gateway 2>&1 | sed -u 's/^/[telegram] /' & \
	uv run python -m services.llm_service 2>&1 | sed -u 's/^/[llm] /' & \
	wait
