
default:
	@echo "Call a specific subcommand:"
	@echo
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null\
	| awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}'\
	| sort\
	| egrep -v -e '^[^[:alnum:]]' -e '^$@$$'
	@echo
	@exit 1

.state/docker-build-base: Dockerfile.dev requirements.txt requirements/base.txt requirements/dev.txt
	# Build our base container for this project.
	docker compose build --build-arg  USER_ID=$(shell id -u)  --build-arg GROUP_ID=$(shell id -g) --force-rm base

	# Collect static assets
	#docker compose run --rm web python manage.py collectstatic --noinput

	# Mark the state so we don't rebuild this needlessly.
	mkdir -p .state
	touch .state/docker-build-base

.state/db-migrated:
	make migrate
	mkdir -p .state && touch .state/db-migrated

.state/db-initialized: .state/docker-build-base .state/db-migrated
	# Mark the state so we don't reload after first launch.
	docker compose run --rm web ./manage.py loaddata fixtures/*.json fixtures/*.json.gz
	mkdir -p .state
	touch .state/db-initialized

serve: .state/db-initialized
	docker compose up --remove-orphans -d

stop:
	docker compose stop

shell: .state/db-initialized
	docker compose run --rm web /bin/bash

dbshell: .state/db-initialized
	docker compose exec postgres psql -U pbaabp pbaabp

manage: .state/db-initialized
	# Run Django manage to accept arbitrary arguments
	docker compose run --rm web ./manage.py $(filter-out $@,$(MAKECMDGOALS))

migrations: .state/db-initialized
	# Run Django makemigrations
	docker compose run --rm web ./manage.py makemigrations

migrate: .state/docker-build-base
	# Run Django migrate
	docker compose run --rm web ./manage.py migrate $(filter-out $@,$(MAKECMDGOALS))

lint: .state/docker-build-base
	docker compose run --rm base isort --check-only .
	docker compose run --rm base black --check .
	docker compose run --rm base flake8

reformat: .state/docker-build-base
	docker compose run --rm base isort .
	docker compose run --rm base black .

test: .state/docker-build-base
	docker compose run --rm web ./manage.py test --keepdb $(filter-out $@,$(MAKECMDGOALS))

check: test lint

clean:
	docker compose down -v
	rm -rf staticroot
	rm -f .state/docker-build-base
	rm -f .state/db-initialized
	rm -f .state/db-migrated
