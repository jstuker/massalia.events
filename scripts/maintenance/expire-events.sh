#!/usr/bin/env bash
#
# expire-events.sh - Mark or remove past events
#
# This script handles event expiration by:
#   - Finding events with dates in the past
#   - Optionally marking them as expired (adds expired: true to front matter)
#   - Optionally deleting expired events and their images
#
# Usage:
#   ./scripts/maintenance/expire-events.sh                   # List expired events
#   ./scripts/maintenance/expire-events.sh --mark            # Mark as expired
#   ./scripts/maintenance/expire-events.sh --delete          # Delete expired events
#   ./scripts/maintenance/expire-events.sh --days 30         # Events older than 30 days
#
# Exit codes:
#   0 - Success
#   1 - Error
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

# Options
ACTION="list"  # list, mark, delete
DAYS_OLD=0     # Events older than this many days (0 = any past event)
DRY_RUN=false
VERBOSE=false

# Counters
TOTAL_EVENTS=0
EXPIRED_EVENTS=0
PROCESSED=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mark|-m)
            ACTION="mark"
            shift
            ;;
        --delete|-d)
            ACTION="delete"
            shift
            ;;
        --days)
            DAYS_OLD="$2"
            shift 2
            ;;
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Find and manage expired events (events with past dates)."
            echo ""
            echo "Options:"
            echo "  --mark, -m     Mark expired events (add expired: true)"
            echo "  --delete, -d   Delete expired events and their images"
            echo "  --days N       Only events older than N days (default: 0 = all past)"
            echo "  --dry-run, -n  Preview changes without modifying files"
            echo "  --verbose, -v  Show detailed output"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Actions:"
            echo "  (default)      List expired events"
            echo "  --mark         Add 'expired: true' to front matter"
            echo "  --delete       Remove event file and associated image"
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
    exit 0
fi

# Calculate cutoff date
if [[ $DAYS_OLD -gt 0 ]]; then
    CUTOFF_DATE=$(date -v-${DAYS_OLD}d +%Y-%m-%d 2>/dev/null || date -d "$DAYS_OLD days ago" +%Y-%m-%d)
else
    CUTOFF_DATE=$(date +%Y-%m-%d)
fi

echo -e "${CYAN}Event Expiration Check${NC}"
echo ""
echo "  Content directory: $CONTENT_DIR"
echo "  Action: $ACTION"
echo "  Cutoff date: $CUTOFF_DATE (events before this are expired)"
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  Mode: ${YELLOW}DRY RUN${NC}"
fi
echo ""

# Function to extract date from front matter
get_event_date() {
    local file="$1"

    # Try to get date field
    local date_value
    date_value=$(sed -n '/^---$/,/^---$/p' "$file" | grep -E "^date:" | head -1 | sed 's/^date:\s*//' | tr -d '"' | tr -d "'")

    # Extract just the date part (YYYY-MM-DD)
    echo "$date_value" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' || echo ""
}

# Function to check if already marked as expired
is_expired() {
    local file="$1"
    sed -n '/^---$/,/^---$/p' "$file" | grep -qE "^expired:\s*true" 2>/dev/null
}

# Function to get image path from front matter
get_image_path() {
    local file="$1"
    local image_value
    image_value=$(sed -n '/^---$/,/^---$/p' "$file" | grep -E "^image:" | head -1 | sed 's/^image:\s*//' | tr -d '"' | tr -d "'")
    echo "$image_value"
}

# Function to mark event as expired
mark_expired() {
    local file="$1"

    if is_expired "$file"; then
        if [[ "$VERBOSE" == "true" ]]; then
            echo "  Already marked as expired"
        fi
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  Would mark as expired"
        return 0
    fi

    # Add expired: true after the first ---
    # Using sed to insert after the opening ---
    local temp_file
    temp_file=$(mktemp)

    awk '
        /^---$/ && !found {
            print
            print "expired: true"
            found = 1
            next
        }
        { print }
    ' "$file" > "$temp_file"

    mv "$temp_file" "$file"
    echo -e "  ${GREEN}Marked as expired${NC}"
    ((PROCESSED++))
}

# Function to delete event
delete_event() {
    local file="$1"
    local relative_path="${file#$PROJECT_ROOT/}"

    # Get associated image
    local image_path
    image_path=$(get_image_path "$file")

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  Would delete: $relative_path"
        if [[ -n "$image_path" ]]; then
            echo "  Would delete image: $image_path"
        fi
        return 0
    fi

    # Delete the event file
    rm -f "$file"
    echo -e "  ${RED}Deleted:${NC} $relative_path"
    ((PROCESSED++))

    # Delete associated image if it exists
    if [[ -n "$image_path" ]]; then
        local full_image_path
        if [[ "$image_path" =~ ^/ ]]; then
            full_image_path="$PROJECT_ROOT/static${image_path}"
        else
            full_image_path="$PROJECT_ROOT/static/$image_path"
        fi

        if [[ -f "$full_image_path" ]]; then
            rm -f "$full_image_path"
            echo -e "  ${RED}Deleted image:${NC} $image_path"
        fi
    fi

    # Remove parent directory if empty
    local parent_dir
    parent_dir=$(dirname "$file")
    if [[ -d "$parent_dir" ]] && [[ -z "$(ls -A "$parent_dir")" ]]; then
        rmdir "$parent_dir" 2>/dev/null || true
    fi
}

# Process each markdown file
echo -e "${CYAN}Scanning events...${NC}"
echo ""

while IFS= read -r -d '' file; do
    ((TOTAL_EVENTS++))

    event_date=$(get_event_date "$file")

    if [[ -z "$event_date" ]]; then
        if [[ "$VERBOSE" == "true" ]]; then
            echo -e "${YELLOW}Warning:${NC} No date found in ${file#$PROJECT_ROOT/}"
        fi
        continue
    fi

    # Compare dates (lexicographic comparison works for YYYY-MM-DD format)
    if [[ "$event_date" < "$CUTOFF_DATE" ]]; then
        ((EXPIRED_EVENTS++))

        # Get event title for display
        local title
        title=$(sed -n '/^---$/,/^---$/p' "$file" | grep -E "^title:" | head -1 | sed 's/^title:\s*//' | tr -d '"')
        title="${title:0:50}"

        echo "Event: $title"
        echo "  Date: $event_date"
        echo "  File: ${file#$PROJECT_ROOT/}"

        case "$ACTION" in
            mark)
                mark_expired "$file"
                ;;
            delete)
                delete_event "$file"
                ;;
            list)
                if is_expired "$file"; then
                    echo -e "  Status: ${YELLOW}already marked expired${NC}"
                else
                    echo -e "  Status: ${RED}not marked${NC}"
                fi
                ;;
        esac

        echo ""
    fi
done < <(find "$CONTENT_DIR" -name "*.md" -type f -print0 2>/dev/null)

# Summary
echo "---"
echo "Total events: $TOTAL_EVENTS"
echo "Expired events: $EXPIRED_EVENTS"

if [[ "$ACTION" != "list" ]]; then
    echo "Processed: $PROCESSED"
fi

if [[ $EXPIRED_EVENTS -eq 0 ]]; then
    echo -e "${GREEN}No expired events found!${NC}"
elif [[ "$ACTION" == "list" ]]; then
    echo ""
    echo "To mark these events as expired, run:"
    echo "  $0 --mark"
    echo ""
    echo "To delete these events, run:"
    echo "  $0 --delete"
fi
