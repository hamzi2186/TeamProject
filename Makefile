up:
	docker compose up --build

down:
	docker compose down

test:
	docker compose run --rm backend pytest
