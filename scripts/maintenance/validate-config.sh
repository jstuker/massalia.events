#!/usr/bin/env bash
#
# validate-config.sh - Validate Hugo configuration files
#
# This script checks Hugo TOML configuration files for syntax errors
# and validates required settings are present.
#
# Usage:
#   ./scripts/maintenance/validate-config.sh
#
# Exit codes:
#   0 - All configurations valid
#   1 - Validation errors found
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

# Track results
ERRORS=0
WARNINGS=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Validate Hugo configuration files for syntax and required settings."
            echo ""
            echo "Options:"
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

echo -e "${CYAN}Validating Hugo Configuration${NC}"
echo ""

# Check if Hugo is installed
if ! command -v hugo &> /dev/null; then
    echo -e "${RED}Error: Hugo is not installed${NC}"
    exit 1
fi

# Function to validate TOML syntax
validate_toml() {
    local file="$1"
    local name="$2"

    echo -n "  $name: "

    if [[ ! -f "$file" ]]; then
        echo -e "${YELLOW}not found${NC}"
        return 0
    fi

    # Use Hugo to validate by attempting to parse
    # Hugo's config command will fail on syntax errors
    if hugo config 2>&1 | grep -q "Error"; then
        echo -e "${RED}syntax error${NC}"
        ((ERRORS++))
        return 1
    fi

    # Basic TOML syntax check using grep for common issues
    local issues=""

    # Check for unclosed brackets
    local open_brackets=$(grep -c '\[' "$file" 2>/dev/null || echo 0)
    local close_brackets=$(grep -c '\]' "$file" 2>/dev/null || echo 0)
    # Note: This is a rough check - TOML section headers have matching brackets

    # Check for lines with = but no value
    if grep -E '^\s*\w+\s*=\s*$' "$file" 2>/dev/null | grep -v '#' | head -1 > /dev/null; then
        issues="${issues}empty value, "
    fi

    if [[ -n "$issues" ]]; then
        echo -e "${YELLOW}warnings: ${issues%, }${NC}"
        ((WARNINGS++))
    else
        echo -e "${GREEN}valid${NC}"
    fi
}

# Function to check required Hugo settings
check_required_settings() {
    echo ""
    echo -e "${CYAN}Checking required settings...${NC}"

    # Get Hugo config as JSON for easier parsing
    local config
    config=$(hugo config 2>/dev/null) || {
        echo -e "${RED}Error: Could not read Hugo configuration${NC}"
        ((ERRORS++))
        return 1
    }

    # Check baseURL
    echo -n "  baseURL: "
    if echo "$config" | grep -q "baseurl"; then
        local baseurl
        baseurl=$(echo "$config" | grep "baseurl" | head -1 | sed 's/.*= //')
        echo -e "${GREEN}$baseurl${NC}"
    else
        echo -e "${YELLOW}not set (will use relative URLs)${NC}"
        ((WARNINGS++))
    fi

    # Check languageCode
    echo -n "  languageCode: "
    if echo "$config" | grep -q "languagecode"; then
        local lang
        lang=$(echo "$config" | grep "languagecode" | head -1 | sed 's/.*= //')
        echo -e "${GREEN}$lang${NC}"
    else
        echo -e "${YELLOW}not set${NC}"
        ((WARNINGS++))
    fi

    # Check title
    echo -n "  title: "
    if echo "$config" | grep -q "^title"; then
        local title
        title=$(echo "$config" | grep "^title" | head -1 | sed 's/.*= //')
        echo -e "${GREEN}$title${NC}"
    else
        echo -e "${YELLOW}not set${NC}"
        ((WARNINGS++))
    fi

    # Check theme
    echo -n "  theme: "
    if echo "$config" | grep -q "theme"; then
        local theme
        theme=$(echo "$config" | grep "theme" | head -1 | sed 's/.*= //')
        echo -e "${GREEN}$theme${NC}"

        # Extract theme name from various formats: 'blowfish', "blowfish", ['blowfish'], blowfish
        local theme_name
        theme_name=$(echo "$theme" | sed "s/\[//g;s/\]//g;s/'//g;s/\"//g" | tr -d '[:space:]')

        # Verify theme exists
        if [[ -n "$theme_name" && ! -d "themes/$theme_name" ]]; then
            echo -e "    ${RED}Warning: Theme directory not found${NC}"
            ((WARNINGS++))
        fi
    else
        echo -e "${YELLOW}not set${NC}"
        ((WARNINGS++))
    fi
}

# Validate main config files
echo "Checking configuration files..."

# Main hugo.toml
validate_toml "hugo.toml" "hugo.toml"

# Config directory files
if [[ -d "config" ]]; then
    for dir in config/*/; do
        if [[ -d "$dir" ]]; then
            env_name=$(basename "$dir")
            echo ""
            echo "Environment: $env_name"

            for file in "$dir"*.toml; do
                if [[ -f "$file" ]]; then
                    validate_toml "$file" "$(basename "$file")"
                fi
            done
        fi
    done
fi

# Check required settings
check_required_settings

# Validate Hugo can build
echo ""
echo -e "${CYAN}Testing Hugo build...${NC}"
echo -n "  Dry run: "

if hugo --gc --minify --destination /tmp/hugo-test-$$ 2>&1 | tail -5 | grep -q "Error"; then
    echo -e "${RED}failed${NC}"
    ((ERRORS++))
    hugo --gc --minify --destination /tmp/hugo-test-$$ 2>&1 | grep -i "error" | head -5
else
    echo -e "${GREEN}success${NC}"
    rm -rf "/tmp/hugo-test-$$"
fi

# Summary
echo ""
echo "---"
if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}All configurations valid!${NC}"
    exit 0
elif [[ $ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}Configuration valid with $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${RED}Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    exit 1
fi
