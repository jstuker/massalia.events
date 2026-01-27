#!/usr/bin/env bash
#
# check-links.sh - Validate internal and external links in the site
#
# This script checks for broken links in the built site. It can validate:
#   - Internal links between pages
#   - External links (optional, slower)
#   - Image references
#
# Usage:
#   ./scripts/maintenance/check-links.sh                    # Check internal links only
#   ./scripts/maintenance/check-links.sh --external         # Also check external links
#   ./scripts/maintenance/check-links.sh --images           # Also verify images exist
#
# Prerequisites:
#   - Site must be built first (run 'make build')
#   - curl (for external link checking)
#
# Exit codes:
#   0 - All links valid
#   1 - Broken links found or error
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
PUBLIC_DIR="$PROJECT_ROOT/public"
CHECK_EXTERNAL=false
CHECK_IMAGES=false
VERBOSE=false

# Counters
TOTAL_LINKS=0
BROKEN_LINKS=0
EXTERNAL_CHECKED=0
EXTERNAL_BROKEN=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --external|-e)
            CHECK_EXTERNAL=true
            shift
            ;;
        --images|-i)
            CHECK_IMAGES=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Validate links in the built Hugo site."
            echo ""
            echo "Options:"
            echo "  --external, -e  Also check external links (slower)"
            echo "  --images, -i    Verify image files exist"
            echo "  --verbose, -v   Show all links being checked"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Note: Run 'make build' first to generate the site."
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

# Check if site is built
if [[ ! -d "$PUBLIC_DIR" ]]; then
    echo -e "${RED}Error: Site not built. Run 'make build' first.${NC}"
    exit 1
fi

echo -e "${CYAN}Checking Links in Built Site${NC}"
echo ""
echo "  Site directory: $PUBLIC_DIR"
echo "  External links: $([ "$CHECK_EXTERNAL" == "true" ] && echo "yes" || echo "no")"
echo "  Image check:    $([ "$CHECK_IMAGES" == "true" ] && echo "yes" || echo "no")"
echo ""

# Find all HTML files
HTML_FILES=$(find "$PUBLIC_DIR" -name "*.html" -type f)
FILE_COUNT=$(echo "$HTML_FILES" | wc -l | tr -d ' ')

echo "Found $FILE_COUNT HTML files to check"
echo ""

# Function to check if internal link target exists
check_internal_link() {
    local source_file="$1"
    local href="$2"

    # Skip anchors, javascript, mailto, tel
    if [[ "$href" =~ ^(#|javascript:|mailto:|tel:) ]]; then
        return 0
    fi

    # Skip external links in this function
    if [[ "$href" =~ ^https?:// ]]; then
        return 0
    fi

    ((TOTAL_LINKS++))

    # Handle relative paths
    local target
    if [[ "$href" =~ ^/ ]]; then
        # Absolute path from site root
        target="$PUBLIC_DIR${href}"
    else
        # Relative path from current file
        local source_dir
        source_dir=$(dirname "$source_file")
        target="$source_dir/$href"
    fi

    # Remove anchor from path
    target="${target%%#*}"

    # Remove query string
    target="${target%%\?*}"

    # Handle directory index
    if [[ -d "$target" ]]; then
        target="$target/index.html"
    elif [[ ! "$target" =~ \.[a-zA-Z]+$ ]]; then
        # No extension, try adding index.html
        if [[ -d "${target%/}" ]]; then
            target="${target%/}/index.html"
        fi
    fi

    # Normalize path
    target=$(realpath -m "$target" 2>/dev/null || echo "$target")

    if [[ "$VERBOSE" == "true" ]]; then
        echo "    Checking: $href -> $target"
    fi

    if [[ ! -f "$target" && ! -d "${target%/index.html}" ]]; then
        echo -e "  ${RED}BROKEN:${NC} $href"
        echo "    Source: ${source_file#$PUBLIC_DIR/}"
        ((BROKEN_LINKS++))
        return 1
    fi

    return 0
}

# Function to check external link
check_external_link() {
    local url="$1"

    ((EXTERNAL_CHECKED++))

    if [[ "$VERBOSE" == "true" ]]; then
        echo "    Checking external: $url"
    fi

    # Use curl with timeout and follow redirects
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "$url" 2>/dev/null || echo "000")

    if [[ "$http_code" =~ ^[23] ]]; then
        return 0
    else
        echo -e "  ${RED}BROKEN (HTTP $http_code):${NC} $url"
        ((EXTERNAL_BROKEN++))
        return 1
    fi
}

# Function to check image references
check_image() {
    local source_file="$1"
    local src="$2"

    # Skip external images and data URIs
    if [[ "$src" =~ ^(https?://|data:) ]]; then
        return 0
    fi

    local target
    if [[ "$src" =~ ^/ ]]; then
        target="$PUBLIC_DIR${src}"
    else
        local source_dir
        source_dir=$(dirname "$source_file")
        target="$source_dir/$src"
    fi

    # Normalize
    target=$(realpath -m "$target" 2>/dev/null || echo "$target")

    if [[ ! -f "$target" ]]; then
        echo -e "  ${RED}MISSING IMAGE:${NC} $src"
        echo "    Source: ${source_file#$PUBLIC_DIR/}"
        ((BROKEN_LINKS++))
        return 1
    fi

    return 0
}

# Process each HTML file
echo -e "${CYAN}Checking internal links...${NC}"

for html_file in $HTML_FILES; do
    if [[ "$VERBOSE" == "true" ]]; then
        echo "  Processing: ${html_file#$PUBLIC_DIR/}"
    fi

    # Extract href attributes (handle both double and single quotes, and = without quotes)
    hrefs=$(grep -oE 'href="[^"]*"|href='\''[^'\'']*'\''|href=[^[:space:]>]+' "$html_file" 2>/dev/null | \
            sed 's/href=//;s/^"//;s/"$//;s/^'\''//;s/'\''$//' || true)

    for href in $hrefs; do
        check_internal_link "$html_file" "$href" || true
    done

    # Check images if requested
    if [[ "$CHECK_IMAGES" == "true" ]]; then
        srcs=$(grep -oE 'src="[^"]*"' "$html_file" 2>/dev/null | sed 's/src="//;s/"$//' || true)

        for src in $srcs; do
            check_image "$html_file" "$src" || true
        done
    fi
done

echo ""
echo "Checked $TOTAL_LINKS internal links"

# Check external links if requested
if [[ "$CHECK_EXTERNAL" == "true" ]]; then
    echo ""
    echo -e "${CYAN}Checking external links...${NC}"
    echo "(This may take a while...)"

    # Collect unique external URLs
    EXTERNAL_URLS=$(grep -rhoE 'href="https?://[^"]*"' "$PUBLIC_DIR" 2>/dev/null | \
                    sed 's/href="//;s/"$//' | \
                    sort -u || true)

    for url in $EXTERNAL_URLS; do
        check_external_link "$url" || true
    done

    echo ""
    echo "Checked $EXTERNAL_CHECKED external links"
fi

# Summary
echo ""
echo "---"

if [[ $BROKEN_LINKS -eq 0 && $EXTERNAL_BROKEN -eq 0 ]]; then
    echo -e "${GREEN}All links valid!${NC}"
    exit 0
else
    total_broken=$((BROKEN_LINKS + EXTERNAL_BROKEN))
    echo -e "${RED}Found $total_broken broken link(s)${NC}"
    [[ $BROKEN_LINKS -gt 0 ]] && echo "  Internal: $BROKEN_LINKS"
    [[ $EXTERNAL_BROKEN -gt 0 ]] && echo "  External: $EXTERNAL_BROKEN"
    exit 1
fi
