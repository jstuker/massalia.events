#!/usr/bin/env bash
#
# update-theme.sh - Check and update Blowfish theme submodule
#
# This script manages the Blowfish Hugo theme which is installed as a git submodule.
# It can check for updates, show the current version, and update to the latest version.
#
# Usage:
#   ./scripts/maintenance/update-theme.sh              # Check for updates
#   ./scripts/maintenance/update-theme.sh --update     # Update to latest version
#   ./scripts/maintenance/update-theme.sh --version    # Show current version only
#
# Exit codes:
#   0 - Success (or no updates available)
#   1 - Error or theme not installed
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Theme configuration
THEME_DIR="$PROJECT_ROOT/themes/blowfish"
THEME_NAME="blowfish"

# Options
DO_UPDATE=false
VERSION_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --update|-u)
            DO_UPDATE=true
            shift
            ;;
        --version|-v)
            VERSION_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Check and update the Blowfish Hugo theme submodule."
            echo ""
            echo "Options:"
            echo "  --update, -u   Update theme to latest version"
            echo "  --version, -v  Show current version only"
            echo "  --help, -h     Show this help message"
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

# Check if theme directory exists
if [[ ! -d "$THEME_DIR" ]]; then
    echo -e "${RED}Error: Theme directory not found at $THEME_DIR${NC}"
    echo ""
    echo "Initialize the theme submodule with:"
    echo "  git submodule update --init --recursive"
    exit 1
fi

# Check if it's a git submodule
if [[ ! -f "$THEME_DIR/.git" && ! -d "$THEME_DIR/.git" ]]; then
    echo -e "${RED}Error: Theme is not a git submodule${NC}"
    echo "Expected git submodule at: $THEME_DIR"
    exit 1
fi

# Get current version from theme.toml or git tag
get_current_version() {
    # Try theme.toml first
    if [[ -f "$THEME_DIR/theme.toml" ]]; then
        local version
        version=$(grep -E "^version\s*=" "$THEME_DIR/theme.toml" 2>/dev/null | \
            sed -E 's/version\s*=\s*"([^"]+)"/\1/' | head -1)
        if [[ -n "$version" ]]; then
            echo "$version"
            return
        fi
    fi

    # Try git describe for tag-based version
    local git_version
    git_version=$(git -C "$THEME_DIR" describe --tags --abbrev=0 2>/dev/null || echo "")
    if [[ -n "$git_version" ]]; then
        echo "$git_version"
        return
    fi

    echo "unknown"
}

# Get current commit hash
get_current_commit() {
    git -C "$THEME_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

# Get latest remote commit
get_latest_commit() {
    git -C "$THEME_DIR" ls-remote origin HEAD 2>/dev/null | cut -c1-7 || echo "unknown"
}

CURRENT_VERSION=$(get_current_version)
CURRENT_COMMIT=$(get_current_commit)

# Version only mode
if [[ "$VERSION_ONLY" == "true" ]]; then
    echo "Theme: $THEME_NAME"
    echo "Version: $CURRENT_VERSION"
    echo "Commit: $CURRENT_COMMIT"
    exit 0
fi

echo -e "${CYAN}Blowfish Theme Status${NC}"
echo ""
echo "  Theme:    $THEME_NAME"
echo "  Version:  $CURRENT_VERSION"
echo "  Commit:   $CURRENT_COMMIT"
echo "  Path:     $THEME_DIR"
echo ""

# Fetch latest from remote
echo -e "${CYAN}Checking for updates...${NC}"
git -C "$THEME_DIR" fetch origin --quiet 2>/dev/null || {
    echo -e "${YELLOW}Warning: Could not fetch from remote${NC}"
    echo "Check your network connection and try again."
    exit 0
}

# Check if there are updates
LOCAL_COMMIT=$(git -C "$THEME_DIR" rev-parse HEAD)
REMOTE_COMMIT=$(git -C "$THEME_DIR" rev-parse origin/main 2>/dev/null || \
                git -C "$THEME_DIR" rev-parse origin/master 2>/dev/null || echo "")

if [[ -z "$REMOTE_COMMIT" ]]; then
    echo -e "${YELLOW}Could not determine remote branch${NC}"
    exit 0
fi

if [[ "$LOCAL_COMMIT" == "$REMOTE_COMMIT" ]]; then
    echo -e "${GREEN}Theme is up to date!${NC}"
    exit 0
fi

# Count commits behind
COMMITS_BEHIND=$(git -C "$THEME_DIR" rev-list --count HEAD..origin/main 2>/dev/null || \
                 git -C "$THEME_DIR" rev-list --count HEAD..origin/master 2>/dev/null || echo "?")

echo -e "${YELLOW}Updates available!${NC}"
echo "  Current: ${LOCAL_COMMIT:0:7}"
echo "  Latest:  ${REMOTE_COMMIT:0:7}"
echo "  Behind:  $COMMITS_BEHIND commit(s)"
echo ""

# Show recent commits
echo "Recent changes:"
git -C "$THEME_DIR" log --oneline HEAD..origin/main 2>/dev/null | head -5 || \
git -C "$THEME_DIR" log --oneline HEAD..origin/master 2>/dev/null | head -5 || true
echo ""

if [[ "$DO_UPDATE" == "true" ]]; then
    echo -e "${CYAN}Updating theme...${NC}"

    # Update submodule
    git submodule update --remote --merge themes/blowfish

    NEW_VERSION=$(get_current_version)
    NEW_COMMIT=$(get_current_commit)

    echo ""
    echo -e "${GREEN}Theme updated successfully!${NC}"
    echo "  New version: $NEW_VERSION"
    echo "  New commit:  $NEW_COMMIT"
    echo ""
    echo "Don't forget to:"
    echo "  1. Test the site: make serve"
    echo "  2. Commit the update: git add themes/blowfish && git commit -m 'Update Blowfish theme'"
else
    echo "To update, run:"
    echo "  $0 --update"
fi
