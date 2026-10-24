.DEFAULT_GOAL := help

.PHONY: help all check fmt lint test coverage snapshots screens screenshots hooks burn-in ui-fmt ui-check ui-build \
	image chart-lint kind-up kind-down

##@ General

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} \
		/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2} \
		/^##@ / {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)}' $(MAKEFILE_LIST)

all: fmt check ## Everything to run before committing: fmt, then check

check: lint test ui-check ## Verify without modifying files: lint, test, the UI's checks (what CI runs)

##@ Development

fmt: ui-fmt ## Run autoformatters (ruff imports and trailing commas, ruff format, rumdl for Markdown, oxfmt for ui/)
	uv run ruff check --select I,COM812 --fix .
	uv run ruff format .
	uv run rumdl fmt .

# ruff owns Python and rumdl Markdown; editorconfig-checker holds every other file to .editorconfig.
# zizmor runs offline, so the lint needs no GitHub token and gives the same answer on every machine.
lint: ## Lint and type check: ruff, pyrefly, rumdl, ec, shellcheck, actionlint, zizmor
	uv run ruff format --check .
	uv run ruff check .
	uv run pyrefly check
	uv run rumdl check .
	uv run ec
	uv run shellcheck $$(git ls-files '*.sh')
	uv run actionlint
	uv run zizmor --offline --quiet .

# One worker per CPU. For one test or a debugger, run `uv run pytest` without -n: it stays serial.
# A test still running after a minute is hung: faulthandler dumps every thread's stack and ends its worker, which fails
# that test by name instead of stalling the run until CI's job timeout.
# COVERAGE=1 also measures coverage and writes coverage.xml, which is how CI feeds Codecov.
PYTEST := uv run pytest -q -n auto -o faulthandler_timeout=60 -o faulthandler_exit_on_timeout=true

test: ## Run all tests, in parallel (COVERAGE=1: also write coverage.xml)
	$(PYTEST) $(if $(COVERAGE),--cov --cov-report=xml)

# Coverage settings live in pyproject.toml ([tool.coverage]). Open htmlcov/index.html for the lines a test never ran.
coverage: ## Run all tests measuring coverage: a summary, htmlcov/, and coverage.xml
	$(PYTEST) --cov --cov-report=term:skip-covered --cov-report=html --cov-report=xml

# Review the diff before committing it: a snapshot is what the tests hold louvre's output to (syrupy). It also deletes
# the snapshots no test reads any more. Serial: syrupy refuses to update under xdist without an experimental file lock.
snapshots: ## Run all tests, recording every snapshot that differs
	uv run pytest -q --snapshot-update

##@ Web UI (ui/; needs Node 22.12+)

ui/node_modules: ui/package.json ui/package-lock.json
	npm --prefix ui ci --no-audit --no-fund
	@touch $@

ui-fmt: ui/node_modules ## Format ui/ with oxfmt
	npm --prefix ui run fmt

# COVERAGE=1 also measures the unit tests' coverage.
ui-check: ui/node_modules ## Check ui/ without changing it: format, lint, types, unit tests, build
	$(if $(COVERAGE),COVERAGE=1 )npm --prefix ui run check

ui-build: ui/node_modules ## Build ui/dist, which `louvre serve` serves under /app/ and the wheel bundles
	npm --prefix ui run build

##@ Screens

# Not part of check: they drive Chromium, over a built ui/ (`make ui-build`). CI runs `screens` as its own job.
# Playwright's Chromium comes from `uv run playwright install chromium`, or set PLAYWRIGHT_CHROMIUM_EXECUTABLE to one
# already on the machine.
SCREENS_TESTS := tests/louvre/web/test_screens.py tests/louvre/web/test_flows.py

screens: ui-build ## Check every page at every screen size: no sideways scroll, no page errors (REQUIREMENTS U4)
	LOUVRE_SCREENS=1 $(PYTEST) $(SCREENS_TESTS)

# Review the diff before committing it: the screenshots are the record of how each page looks on each screen.
screenshots: ui-build ## Check every page at every screen size, and rewrite docs/screenshots and its gallery
	LOUVRE_SCREENS=update $(PYTEST) $(SCREENS_TESTS)

##@ Flaky tests

# For when a test is suspected of being flaky, and to prove a fix for one: this runs the test files a change touched
# many times over, and fails if any run does. BASE is what the change is measured from, by default where this branch
# left origin/main; ALL=1 runs every test instead. REPEAT is how many times each runs.
BASE ?= $(shell git merge-base origin/main HEAD 2>/dev/null)
REPEAT ?= 10

# Whole runs one after another, not pytest-repeat's parametrized copies: those rename each test, so no syrupy snapshot
# matches, and each run here also spreads the tests across xdist's workers in a different order.
burn-in: ## Run each test file changed since BASE (ALL=1: every one) REPEAT times, the whole file each time
	@test -n "$(ALL)$(BASE)" || { echo "BASE is empty: fetch origin/main, or pass BASE=ref or ALL=1"; exit 1; }
	@files=$$($(if $(ALL),echo tests,git diff --name-only --diff-filter=AMR $(BASE) -- 'tests/*test_*.py')); \
	if [ -z "$$files" ]; then echo "No test file changed since $(BASE)."; exit 0; fi; \
	for i in $$(seq $(REPEAT)); do \
		echo "Run $$i of $(REPEAT):" $$files; \
		$(PYTEST) $$files || { echo "Failed on run $$i of $(REPEAT): flaky, or broken."; exit 1; }; \
	done

##@ Deploy (needs Docker; helm and kind for the chart)

# The image's version, from git as the wheel's is (D004): the build context carries no .git, so it goes in as a
# build argument.
IMAGE ?= louvre:dev
VERSION ?= $(shell uvx -q --from uv-dynamic-versioning==0.14.1 uv-dynamic-versioning)
CHART := charts/louvre
KIND_CLUSTER ?= louvre

image: ## Build the container image, as IMAGE (louvre:dev)
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE) .

# Each example values file, as well as the defaults: a template that fails to render for one of them fails here.
chart-lint: ## Lint the Helm chart and render it with each example values file
	helm lint --strict $(CHART)
	@for values in $(CHART)/examples/*.yaml; do \
		echo "helm lint and template with $$values"; \
		helm lint --strict --quiet $(CHART) -f $$values && helm template louvre $(CHART) -f $$values >/dev/null || exit 1; \
	done

# The image goes into the cluster's nodes, so nothing is pushed or pulled; then the chart's own test checks Louvre and
# its bundled PostgreSQL. Run it again after a change: it rebuilds, reloads, and upgrades in place.
kind-up: image ## Run Louvre and a bundled PostgreSQL on a local kind cluster, and test the release
	kind get clusters | grep -qx $(KIND_CLUSTER) || kind create cluster --name $(KIND_CLUSTER) --wait 120s
	kind load docker-image $(IMAGE) --name $(KIND_CLUSTER)
	helm upgrade --install louvre $(CHART) --kube-context kind-$(KIND_CLUSTER) -f $(CHART)/examples/local.yaml \
		--set image.repository=$(word 1,$(subst :, ,$(IMAGE))) --set image.tag=$(word 2,$(subst :, ,$(IMAGE))) \
		--wait --timeout 5m
	kubectl --context kind-$(KIND_CLUSTER) rollout restart deployment/louvre
	kubectl --context kind-$(KIND_CLUSTER) rollout status deployment/louvre --timeout 2m
	helm test louvre --kube-context kind-$(KIND_CLUSTER) --logs
	@echo "kubectl --context kind-$(KIND_CLUSTER) port-forward svc/louvre 8000:80, then open http://127.0.0.1:8000/"

kind-down: ## Delete the local kind cluster, its database with it
	kind delete cluster --name $(KIND_CLUSTER)

##@ Setup

# Optional: CI's `make check` runs every check anyway. prek.toml says which hook runs what.
hooks: ## Install git hooks (prek): the formatters and linters on each commit
	uv run prek install
