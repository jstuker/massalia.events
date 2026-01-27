#!/usr/bin/env bash
#
# build.sh - Build the Hugo site for production
#
# This script builds the site with the same flags used in CI/CD,
# producing a production-ready site in the public/ directory.
#
# Usage:
#   ./scripts/build.sh              # Standard production build
#   ./scripts/build.sh --drafts     # Include draft content
#   ./scripts/build.sh --baseURL https://example.com
#
# Environment variables:
#   HUGO_BASEURL - Override the base URL (optional)
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default settings (matching CI workflow)
HUGO_FLAGS="--gc --minify"
INCLUDE_DRAFTS=false
BASE_URL=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --drafts|-D)
            INCLUDE_DRAFTS=true
            shift
            ;;
        --baseURL)
            BASE_URL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Build the Hugo site for production."
            echo ""
            echo "Options:"
            echo "  --drafts, -D    Include draft content"
            echo "  --baseURL URL   Override the base URL"
            echo "  --help, -h      Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Check for Hugo
if ! command -v hugo &> /dev/null; then
    echo -e "${RED}Error: Hugo is not installed${NC}"
    echo "Please install Hugo extended version 0.154.4 or later"
    echo "  macOS: brew install hugo"
    echo "  See: https://gohugo.io/installation/"
    exit 1
fi

# Verify Hugo is extended version
HUGO_VERSION=$(hugo version)
if [[ ! "$HUGO_VERSION" == *"extended"* ]]; then
    echo -e "${YELLOW}Warning: Hugo extended version is recommended${NC}"
fi

echo -e "${GREEN}Building Hugo site...${NC}"

# Build flags
BUILD_FLAGS="$HUGO_FLAGS"

if [[ "$INCLUDE_DRAFTS" == "true" ]]; then
    BUILD_FLAGS="$BUILD_FLAGS --buildDrafts"
    echo "  Including draft content"
fi

if [[ -n "$BASE_URL" ]]; then
    BUILD_FLAGS="$BUILD_FLAGS --baseURL $BASE_URL"
    echo "  Base URL: $BASE_URL"
elif [[ -n "${HUGO_BASEURL:-}" ]]; then
    BUILD_FLAGS="$BUILD_FLAGS --baseURL $HUGO_BASEURL"
    echo "  Base URL: $HUGO_BASEURL (from environment)"
fi

# Run Hugo build
echo "  Flags: $BUILD_FLAGS"
echo ""

# shellcheck disable=SC2086
hugo $BUILD_FLAGS

# Report success
if [[ -d "public" ]]; then
    FILE_COUNT=$(find public -type f | wc -l | tr -d ' ')
    echo ""
    echo -e "${GREEN}Build complete!${NC}"
    echo "  Output: $PROJECT_ROOT/public/"
    echo "  Files: $FILE_COUNT"
else
    echo -e "${RED}Build failed: public/ directory not created${NC}"
    exit 1
fi
