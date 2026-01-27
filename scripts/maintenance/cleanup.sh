#!/usr/bin/env bash
#
# cleanup.sh - Remove stale build artifacts and temporary files
#
# This script cleans up various temporary and generated files including:
#   - Hugo build artifacts (public/, resources/_gen/)
#   - Editor backup files (*~, *.swp, *.swo)
#   - OS-generated files (.DS_Store, Thumbs.db)
#   - Python cache files (__pycache__, *.pyc)
#   - Orphaned images (images not referenced by any event)
#
# Usage:
#   ./scripts/maintenance/cleanup.sh                # Clean standard artifacts
#   ./scripts/maintenance/cleanup.sh --all          # Also clean orphaned images
#   ./scripts/maintenance/cleanup.sh --dry-run      # Preview what would be deleted
#
# Exit codes:
#   0 - Cleanup successful
#   1 - Error during cleanup
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

# Options
DRY_RUN=false
CLEAN_ALL=false
VERBOSE=false

# Counters
FILES_REMOVED=0
DIRS_REMOVED=0
SPACE_FREED=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --all|-a)
            CLEAN_ALL=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Remove stale build artifacts and temporary files."
            echo ""
            echo "Options:"
            echo "  --dry-run, -n  Preview what would be deleted without removing"
            echo "  --all, -a      Also clean orphaned images"
            echo "  --verbose, -v  Show each file being removed"
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

echo -e "${CYAN}Cleanup: Removing Stale Files${NC}"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}DRY RUN - No files will be deleted${NC}"
    echo ""
fi

# Function to remove file or directory
remove_item() {
    local item="$1"
    local type="$2"  # "file" or "dir"

    if [[ ! -e "$item" ]]; then
        return 0
    fi

    local size=0
    if [[ "$type" == "file" ]]; then
        size=$(stat -f%z "$item" 2>/dev/null || stat -c%s "$item" 2>/dev/null || echo 0)
    elif [[ "$type" == "dir" ]]; then
        size=$(du -sk "$item" 2>/dev/null | cut -f1 || echo 0)
        size=$((size * 1024))
    fi

    if [[ "$VERBOSE" == "true" || "$DRY_RUN" == "true" ]]; then
        echo "  $([ "$DRY_RUN" == "true" ] && echo "Would remove" || echo "Removing"): ${item#$PROJECT_ROOT/}"
    fi

    if [[ "$DRY_RUN" != "true" ]]; then
        if [[ "$type" == "file" ]]; then
            rm -f "$item"
            ((FILES_REMOVED++))
        else
            rm -rf "$item"
            ((DIRS_REMOVED++))
        fi
    fi

    ((SPACE_FREED += size))
}

# 1. Hugo build artifacts
echo "Hugo build artifacts..."
remove_item "$PROJECT_ROOT/public" "dir"
remove_item "$PROJECT_ROOT/resources/_gen" "dir"
remove_item "$PROJECT_ROOT/.hugo_build.lock" "file"

# 2. Editor backup files
echo "Editor backup files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "file"
done < <(find "$PROJECT_ROOT" -type f \( -name "*~" -o -name "*.swp" -o -name "*.swo" -o -name "*.bak" \) -print0 2>/dev/null || true)

# 3. OS-generated files
echo "OS-generated files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "file"
done < <(find "$PROJECT_ROOT" -type f \( -name ".DS_Store" -o -name "Thumbs.db" -o -name "desktop.ini" \) -print0 2>/dev/null || true)

# 4. Python cache files (in crawler directory, excluding venv)
echo "Python cache files..."
if [[ -d "$PROJECT_ROOT/crawler" ]]; then
    while IFS= read -r -d '' dir; do
        remove_item "$dir" "dir"
    done < <(find "$PROJECT_ROOT/crawler" -path "*/venv" -prune -o -type d -name "__pycache__" -print0 2>/dev/null || true)

    while IFS= read -r -d '' file; do
        remove_item "$file" "file"
    done < <(find "$PROJECT_ROOT/crawler" -path "*/venv" -prune -o -type f -name "*.pyc" -print0 2>/dev/null || true)

    # pytest cache
    remove_item "$PROJECT_ROOT/crawler/.pytest_cache" "dir"

    # ruff cache
    remove_item "$PROJECT_ROOT/crawler/.ruff_cache" "dir"
fi

# 5. Empty directories in content (but not the content directory itself)
echo "Empty directories..."
if [[ -d "$PROJECT_ROOT/content/events" ]]; then
    while IFS= read -r -d '' dir; do
        if [[ "$dir" != "$PROJECT_ROOT/content/events" && "$dir" != "$PROJECT_ROOT/content" ]]; then
            remove_item "$dir" "dir"
        fi
    done < <(find "$PROJECT_ROOT/content/events" -type d -empty -print0 2>/dev/null || true)
fi

# 6. Orphaned images (only with --all flag)
if [[ "$CLEAN_ALL" == "true" ]]; then
    echo "Checking for orphaned images..."

    IMAGES_DIR="$PROJECT_ROOT/static/images/events"
    CONTENT_DIR="$PROJECT_ROOT/content/events"

    if [[ -d "$IMAGES_DIR" && -d "$CONTENT_DIR" ]]; then
        # Get all images
        while IFS= read -r -d '' image; do
            image_name=$(basename "$image")

            # Check if any markdown file references this image
            if ! grep -rq "$image_name" "$CONTENT_DIR" 2>/dev/null; then
                echo -e "  ${YELLOW}Orphaned:${NC} $image_name"
                remove_item "$image" "file"
            fi
        done < <(find "$IMAGES_DIR" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.webp" -o -name "*.gif" \) -print0 2>/dev/null || true)
    fi
fi

# Format size for display
format_size() {
    local size=$1
    if [[ $size -ge 1073741824 ]]; then
        echo "$(echo "scale=2; $size/1073741824" | bc)GB"
    elif [[ $size -ge 1048576 ]]; then
        echo "$(echo "scale=2; $size/1048576" | bc)MB"
    elif [[ $size -ge 1024 ]]; then
        echo "$(echo "scale=2; $size/1024" | bc)KB"
    else
        echo "${size}B"
    fi
}

# Summary
echo ""
echo "---"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}Dry run complete${NC}"
    echo "Would remove:"
    echo "  Files: $FILES_REMOVED"
    echo "  Directories: $DIRS_REMOVED"
    echo "  Space: $(format_size $SPACE_FREED)"
else
    if [[ $FILES_REMOVED -eq 0 && $DIRS_REMOVED -eq 0 ]]; then
        echo -e "${GREEN}Already clean - nothing to remove${NC}"
    else
        echo -e "${GREEN}Cleanup complete!${NC}"
        echo "Removed:"
        echo "  Files: $FILES_REMOVED"
        echo "  Directories: $DIRS_REMOVED"
        echo "  Space freed: $(format_size $SPACE_FREED)"
    fi
fi
