# Makefile for massalia.events
#
# Common targets for building and developing the Hugo site.
# Run 'make help' to see available targets.
#

.PHONY: help build serve clean check install crawl crawl-preview \
        update-theme check-theme validate-config check-links check-links-all \
        validate-content cleanup cleanup-all expire-events mark-expired \
        delete-expired maintenance

# Default target
.DEFAULT_GOAL := help

# Colors for help output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

## help: Show this help message
help:
	@echo "$(CYAN)massalia.events Makefile$(NC)"
	@echo ""
	@echo "$(GREEN)Usage:$(NC)"
	@echo "  make <target>"
	@echo ""
	@echo "$(GREEN)Targets:$(NC)"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed -E 's/## /  /' | sed -E 's/: /\t/'

## build: Build the site for production
build:
	@./scripts/build.sh

## build-drafts: Build the site including draft content
build-drafts:
	@./scripts/build.sh --drafts

## serve: Start development server at localhost:1313
serve:
	@./scripts/serve.sh

## serve-network: Start development server accessible on network
serve-network:
	@./scripts/serve.sh --network

## serve-production: Start server without drafts (preview production)
serve-production:
	@./scripts/serve.sh --no-drafts --no-future

## clean: Remove build artifacts (public/, resources/_gen/)
clean:
	@./scripts/clean.sh

## clean-all: Remove all generated files including node_modules
clean-all:
	@./scripts/clean.sh --all

## check: Verify all dependencies are installed
check:
	@./scripts/check-deps.sh

## install: Install Node.js dependencies (if package.json exists)
install:
	@if [ -f package.json ]; then npm install; else echo "No package.json found"; fi

## crawl: Run the event crawler
crawl:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && python crawl.py run

## crawl-preview: Preview crawler results (dry run)
crawl-preview:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && python crawl.py run --dry-run

## crawl-status: Show last crawl status
crawl-status:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && python crawl.py status

## validate: Validate crawler configuration
validate:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && python crawl.py validate

## test: Run all tests (crawler tests)
test:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && python -m pytest

## lint: Run linters (crawler code)
lint:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && ruff check .

## format: Format code (crawler code)
format:
	@cd crawler && source venv/bin/activate 2>/dev/null || true && ruff format .

## submodules: Initialize git submodules (theme)
submodules:
	@git submodule update --init --recursive

## deploy-preview: Build and open site locally
deploy-preview: clean build
	@echo "Opening site preview..."
	@open public/index.html 2>/dev/null || xdg-open public/index.html 2>/dev/null || echo "Open public/index.html in your browser"

## all: Check dependencies, clean, and build
all: check clean build
	@echo "Build complete!"

# =============================================================================
# Maintenance Targets
# =============================================================================

## update-theme: Check and update Blowfish theme to latest version
update-theme:
	@./scripts/maintenance/update-theme.sh

## check-theme: Show current theme version and check for updates
check-theme:
	@./scripts/maintenance/update-theme.sh --version

## validate-config: Validate Hugo configuration files
validate-config:
	@./scripts/maintenance/validate-config.sh

## check-links: Check for broken internal links (run 'make build' first)
check-links:
	@./scripts/maintenance/check-links.sh

## check-links-all: Check internal and external links
check-links-all:
	@./scripts/maintenance/check-links.sh --external --images

## validate-content: Validate event markdown files
validate-content:
	@./scripts/maintenance/validate-content.sh

## cleanup: Remove stale build artifacts and temporary files
cleanup:
	@./scripts/maintenance/cleanup.sh

## cleanup-all: Full cleanup including orphaned images
cleanup-all:
	@./scripts/maintenance/cleanup.sh --all

## expire-events: List expired events (past dates)
expire-events:
	@./scripts/maintenance/expire-events.sh

## mark-expired: Mark past events as expired
mark-expired:
	@./scripts/maintenance/expire-events.sh --mark

## delete-expired: Delete expired events (use with caution)
delete-expired:
	@./scripts/maintenance/expire-events.sh --delete

## maintenance: Run all maintenance checks
maintenance: validate-config validate-content check-theme
	@echo ""
	@echo "Maintenance checks complete!"
