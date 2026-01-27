#!/usr/bin/env bash
#
# check-deps.sh - Check dependencies for building the Hugo site
#
# This script verifies that all required tools are installed and
# at the expected versions.
#
# Usage:
#   ./scripts/check-deps.sh
#
# Exit codes:
#   0 - All dependencies satisfied
#   1 - One or more dependencies missing
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Minimum versions (matching CI workflow)
MIN_HUGO_VERSION="0.154.0"
MIN_GO_VERSION="1.21.0"
MIN_NODE_VERSION="18.0.0"

# Track results
ALL_OK=true

# Version comparison function (returns 0 if $1 >= $2)
version_gte() {
    printf '%s\n%s' "$2" "$1" | sort -V -C
}

echo -e "${CYAN}Checking dependencies for massalia.events...${NC}"
echo ""

# Check Hugo
echo -n "Hugo:      "
if command -v hugo &> /dev/null; then
    HUGO_OUTPUT=$(hugo version 2>&1)
    HUGO_VERSION=$(echo "$HUGO_OUTPUT" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | tr -d 'v')
    HUGO_EXTENDED=$(echo "$HUGO_OUTPUT" | grep -q "extended" && echo "extended" || echo "standard")

    if version_gte "$HUGO_VERSION" "$MIN_HUGO_VERSION"; then
        echo -e "${GREEN}$HUGO_VERSION ($HUGO_EXTENDED)${NC}"
        if [[ "$HUGO_EXTENDED" != "extended" ]]; then
            echo -e "  ${YELLOW}Warning: Hugo extended version recommended for SCSS support${NC}"
        fi
    else
        echo -e "${YELLOW}$HUGO_VERSION (minimum: $MIN_HUGO_VERSION)${NC}"
        ALL_OK=false
    fi
else
    echo -e "${RED}Not installed${NC}"
    echo "  Install: brew install hugo"
    echo "  Or: https://gohugo.io/installation/"
    ALL_OK=false
fi

# Check Go (optional, for Hugo modules)
echo -n "Go:        "
if command -v go &> /dev/null; then
    GO_VERSION=$(go version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if version_gte "$GO_VERSION" "$MIN_GO_VERSION"; then
        echo -e "${GREEN}$GO_VERSION${NC}"
    else
        echo -e "${YELLOW}$GO_VERSION (minimum: $MIN_GO_VERSION)${NC}"
    fi
else
    echo -e "${YELLOW}Not installed (optional, for Hugo modules)${NC}"
    echo "  Install: brew install go"
fi

# Check Node.js (optional)
echo -n "Node.js:   "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version | tr -d 'v')
    if version_gte "$NODE_VERSION" "$MIN_NODE_VERSION"; then
        echo -e "${GREEN}$NODE_VERSION${NC}"
    else
        echo -e "${YELLOW}$NODE_VERSION (minimum: $MIN_NODE_VERSION)${NC}"
    fi
else
    echo -e "${YELLOW}Not installed (optional)${NC}"
fi

# Check Git
echo -n "Git:       "
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    echo -e "${GREEN}$GIT_VERSION${NC}"
else
    echo -e "${RED}Not installed${NC}"
    echo "  Install: brew install git"
    ALL_OK=false
fi

# Check Dart Sass (optional)
echo -n "Dart Sass: "
if command -v sass &> /dev/null; then
    SASS_VERSION=$(sass --version 2>/dev/null | head -1)
    echo -e "${GREEN}$SASS_VERSION${NC}"
else
    echo -e "${YELLOW}Not installed (Hugo has embedded Sass)${NC}"
fi

# Check for submodules
echo ""
echo -n "Theme:     "
if [[ -d "themes/blowfish" && -f "themes/blowfish/theme.toml" ]]; then
    THEME_VERSION=$(grep "version" themes/blowfish/theme.toml 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
    echo -e "${GREEN}blowfish v$THEME_VERSION${NC}"
else
    echo -e "${RED}Blowfish theme not found${NC}"
    echo "  Run: git submodule update --init --recursive"
    ALL_OK=false
fi

# Summary
echo ""
echo "---"
if [[ "$ALL_OK" == "true" ]]; then
    echo -e "${GREEN}All required dependencies are installed!${NC}"
    exit 0
else
    echo -e "${RED}Some dependencies are missing or outdated.${NC}"
    echo "Please install the missing dependencies and try again."
    exit 1
fi
