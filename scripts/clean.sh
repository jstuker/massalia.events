#!/usr/bin/env bash
#
# clean.sh - Clean Hugo build artifacts
#
# This script removes build artifacts including:
#   - public/           (generated site)
#   - resources/_gen/   (generated resources)
#   - .hugo_build.lock  (build lock file)
#
# Usage:
#   ./scripts/clean.sh          # Clean build artifacts
#   ./scripts/clean.sh --all    # Also clean node_modules
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

# Options
CLEAN_ALL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all|-a)
            CLEAN_ALL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Clean Hugo build artifacts."
            echo ""
            echo "Options:"
            echo "  --all, -a    Also clean node_modules"
            echo "  --help, -h   Show this help message"
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

echo -e "${GREEN}Cleaning build artifacts...${NC}"

# Track what was cleaned
CLEANED=()

# Clean public directory
if [[ -d "public" ]]; then
    rm -rf public
    CLEANED+=("public/")
fi

# Clean resources/_gen directory
if [[ -d "resources/_gen" ]]; then
    rm -rf resources/_gen
    CLEANED+=("resources/_gen/")
fi

# Clean Hugo build lock
if [[ -f ".hugo_build.lock" ]]; then
    rm -f .hugo_build.lock
    CLEANED+=(".hugo_build.lock")
fi

# Clean node_modules if --all flag
if [[ "$CLEAN_ALL" == "true" ]]; then
    if [[ -d "node_modules" ]]; then
        rm -rf node_modules
        CLEANED+=("node_modules/")
    fi
fi

# Report results
echo ""
if [[ ${#CLEANED[@]} -eq 0 ]]; then
    echo -e "${YELLOW}Nothing to clean - already clean!${NC}"
else
    echo "Removed:"
    for item in "${CLEANED[@]}"; do
        echo "  - $item"
    done
    echo ""
    echo -e "${GREEN}Clean complete!${NC}"
fi
