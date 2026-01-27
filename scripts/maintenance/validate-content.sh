#!/usr/bin/env bash
#
# validate-content.sh - Validate event content front matter
#
# This script checks event markdown files for:
#   - Required front matter fields
#   - Valid date formats
#   - Valid category values
#   - Image file existence
#
# Usage:
#   ./scripts/maintenance/validate-content.sh              # Validate all events
#   ./scripts/maintenance/validate-content.sh --fix        # Auto-fix common issues
#   ./scripts/maintenance/validate-content.sh --verbose    # Show all files checked
#
# Exit codes:
#   0 - All content valid
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

# Configuration
CONTENT_DIR="$PROJECT_ROOT/content/events"
IMAGES_DIR="$PROJECT_ROOT/static/images/events"
FIX_MODE=false
VERBOSE=false

# Required front matter fields
REQUIRED_FIELDS=("title" "date" "categories")

# Valid categories
VALID_CATEGORIES=("danse" "musique" "theatre" "art" "communaute")

# Counters
TOTAL_FILES=0
ERRORS=0
WARNINGS=0
FIXED=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix|-f)
            FIX_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Validate event markdown files for required fields and valid values."
            echo ""
            echo "Options:"
            echo "  --fix, -f      Auto-fix common issues where possible"
            echo "  --verbose, -v  Show all files being checked"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Required front matter fields:"
            for field in "${REQUIRED_FIELDS[@]}"; do
                echo "  - $field"
            done
            echo ""
            echo "Valid categories:"
            for cat in "${VALID_CATEGORIES[@]}"; do
                echo "  - $cat"
            done
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

# Check if content directory exists
if [[ ! -d "$CONTENT_DIR" ]]; then
    echo -e "${YELLOW}No events directory found at $CONTENT_DIR${NC}"
    echo "This is normal for a fresh installation."
    exit 0
fi

echo -e "${CYAN}Validating Event Content${NC}"
echo ""
echo "  Content directory: $CONTENT_DIR"
echo "  Fix mode: $([ "$FIX_MODE" == "true" ] && echo "yes" || echo "no")"
echo ""

# Function to extract front matter value
get_frontmatter_value() {
    local file="$1"
    local field="$2"

    # Extract value between --- markers, trim leading/trailing whitespace
    # This handles simple key: value pairs
    sed -n '/^---$/,/^---$/p' "$file" | grep -E "^${field}:" | head -1 | sed "s/^${field}:\s*//" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Function to check if front matter has a field (even if array)
has_frontmatter_field() {
    local file="$1"
    local field="$2"

    sed -n '/^---$/,/^---$/p' "$file" | grep -qE "^${field}:" 2>/dev/null
}

# Function to extract categories from front matter (handles both inline and multiline)
get_categories() {
    local file="$1"

    # First try inline array format: categories: ["danse", "musique"]
    local inline
    inline=$(sed -n '/^---$/,/^---$/p' "$file" | grep -E "^categories:\s*\[" | head -1 | \
             sed 's/categories:\s*\[//;s/\]//;s/"//g;s/'\''//g;s/,/ /g')

    if [[ -n "$inline" ]]; then
        echo "$inline"
        return
    fi

    # Try multi-line YAML array format
    sed -n '/^---$/,/^---$/p' "$file" | \
        awk '/^categories:/{found=1; next} found && /^[a-zA-Z]/{exit} found && /^\s*-/{gsub(/^\s*-\s*/, ""); gsub(/"/, ""); gsub(/'\''/, ""); print}' | \
        tr '\n' ' '
}

# Function to check if value exists in array
in_array() {
    local value="$1"
    shift
    local arr=("$@")

    for item in "${arr[@]}"; do
        if [[ "$item" == "$value" ]]; then
            return 0
        fi
    done
    return 1
}

# Function to validate a single file
validate_file() {
    local file="$1"
    local relative_path="${file#$PROJECT_ROOT/}"
    local file_errors=0
    local file_warnings=0

    ((TOTAL_FILES++))

    if [[ "$VERBOSE" == "true" ]]; then
        echo "  Checking: $relative_path"
    fi

    # Check if file has front matter
    if ! head -1 "$file" | grep -q "^---$"; then
        echo -e "  ${RED}ERROR:${NC} No front matter found"
        echo "    File: $relative_path"
        ((ERRORS++))
        return 1
    fi

    # Check required fields
    for field in "${REQUIRED_FIELDS[@]}"; do
        # Special handling for categories which can be an array
        if [[ "$field" == "categories" ]]; then
            if ! has_frontmatter_field "$file" "categories"; then
                echo -e "  ${RED}ERROR:${NC} Missing required field '$field'"
                echo "    File: $relative_path"
                ((file_errors++))
            fi
        else
            local value
            value=$(get_frontmatter_value "$file" "$field")

            if [[ -z "$value" ]]; then
                echo -e "  ${RED}ERROR:${NC} Missing required field '$field'"
                echo "    File: $relative_path"
                ((file_errors++))
            fi
        fi
    done

    # Validate date format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    local date_value
    date_value=$(get_frontmatter_value "$file" "date")
    if [[ -n "$date_value" ]]; then
        # Remove quotes if present
        date_value="${date_value//\"/}"
        date_value="${date_value//\'/}"

        if ! [[ "$date_value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2})?.*$ ]]; then
            echo -e "  ${YELLOW}WARNING:${NC} Invalid date format '$date_value'"
            echo "    File: $relative_path"
            echo "    Expected: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
            ((file_warnings++))
        fi
    fi

    # Validate categories
    local cats
    cats=$(get_categories "$file")

    if [[ -n "$cats" ]]; then
        for cat in $cats; do
            cat="${cat//\"/}"
            cat="${cat//\'/}"
            cat=$(echo "$cat" | tr -d '[:space:]')

            if [[ -n "$cat" ]] && ! in_array "$cat" "${VALID_CATEGORIES[@]}"; then
                echo -e "  ${YELLOW}WARNING:${NC} Unknown category '$cat'"
                echo "    File: $relative_path"
                echo "    Valid: ${VALID_CATEGORIES[*]}"
                ((file_warnings++))
            fi
        done
    fi

    # Check image reference if present and not empty
    local image_value
    image_value=$(get_frontmatter_value "$file" "image")
    image_value="${image_value//\"/}"
    image_value="${image_value//\'/}"
    image_value=$(echo "$image_value" | tr -d '[:space:]')

    if [[ -n "$image_value" ]]; then
        # Handle relative and absolute paths
        local image_path
        if [[ "$image_value" =~ ^/ ]]; then
            image_path="$PROJECT_ROOT/static${image_value}"
        else
            image_path="$PROJECT_ROOT/static/$image_value"
        fi

        if [[ ! -f "$image_path" ]]; then
            echo -e "  ${YELLOW}WARNING:${NC} Image not found '$image_value'"
            echo "    File: $relative_path"
            ((file_warnings++))
        fi
    fi

    # Check for draft status
    local draft_value
    draft_value=$(get_frontmatter_value "$file" "draft")
    if [[ "$draft_value" == "true" ]]; then
        if [[ "$VERBOSE" == "true" ]]; then
            echo -e "    ${YELLOW}Note:${NC} File is marked as draft"
        fi
    fi

    # Update global counters
    ((ERRORS += file_errors))
    ((WARNINGS += file_warnings))

    return $file_errors
}

# Find and validate all markdown files
echo -e "${CYAN}Scanning event files...${NC}"
echo ""

# Use find to get all .md files (excluding _index files which are section pages)
while IFS= read -r -d '' file; do
    # Skip _index files (Hugo section pages)
    if [[ "$(basename "$file")" == _index* ]]; then
        if [[ "$VERBOSE" == "true" ]]; then
            echo "  Skipping section page: ${file#$PROJECT_ROOT/}"
        fi
        continue
    fi
    validate_file "$file" || true
done < <(find "$CONTENT_DIR" -name "*.md" -type f -print0 2>/dev/null)

# Summary
echo ""
echo "---"
echo "Files checked: $TOTAL_FILES"

if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}All content valid!${NC}"
    exit 0
elif [[ $ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}Content valid with $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${RED}Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    exit 1
fi
