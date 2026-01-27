#!/usr/bin/env bash
#
# serve.sh - Start Hugo development server
#
# This script starts a local development server with live reload.
# By default, it shows draft content and binds to localhost:1313.
#
# Usage:
#   ./scripts/serve.sh              # Start server at localhost:1313
#   ./scripts/serve.sh --network    # Allow network access (0.0.0.0)
#   ./scripts/serve.sh --no-drafts  # Exclude draft content
#   ./scripts/serve.sh --port 8080  # Use custom port
#
# Press Ctrl+C to stop the server.
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
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default settings
INCLUDE_DRAFTS=true
INCLUDE_FUTURE=true
BIND_ADDRESS="localhost"
PORT="1313"
DISABLE_FAST_RENDER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-drafts)
            INCLUDE_DRAFTS=false
            shift
            ;;
        --no-future)
            INCLUDE_FUTURE=false
            shift
            ;;
        --network|-n)
            BIND_ADDRESS="0.0.0.0"
            shift
            ;;
        --port|-p)
            PORT="$2"
            shift 2
            ;;
        --disable-fast-render)
            DISABLE_FAST_RENDER=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Start the Hugo development server with live reload."
            echo ""
            echo "Options:"
            echo "  --no-drafts            Exclude draft content"
            echo "  --no-future            Exclude future-dated content"
            echo "  --network, -n          Allow network access (bind to 0.0.0.0)"
            echo "  --port, -p PORT        Use custom port (default: 1313)"
            echo "  --disable-fast-render  Disable fast render (full rebuild on changes)"
            echo "  --help, -h             Show this help message"
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

echo -e "${GREEN}Starting Hugo development server...${NC}"
echo ""

# Build serve flags
SERVE_FLAGS="--bind $BIND_ADDRESS --port $PORT"

if [[ "$INCLUDE_DRAFTS" == "true" ]]; then
    SERVE_FLAGS="$SERVE_FLAGS --buildDrafts"
    echo "  Drafts: ${GREEN}included${NC}"
else
    echo "  Drafts: ${YELLOW}excluded${NC}"
fi

if [[ "$INCLUDE_FUTURE" == "true" ]]; then
    SERVE_FLAGS="$SERVE_FLAGS --buildFuture"
    echo "  Future: ${GREEN}included${NC}"
else
    echo "  Future: ${YELLOW}excluded${NC}"
fi

if [[ "$DISABLE_FAST_RENDER" == "true" ]]; then
    SERVE_FLAGS="$SERVE_FLAGS --disableFastRender"
    echo "  Fast render: ${YELLOW}disabled${NC}"
else
    echo "  Fast render: ${GREEN}enabled${NC}"
fi

echo ""

# Display URL
if [[ "$BIND_ADDRESS" == "0.0.0.0" ]]; then
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "your-ip")
    echo -e "${CYAN}Server will be available at:${NC}"
    echo "  Local:   http://localhost:$PORT"
    echo "  Network: http://$LOCAL_IP:$PORT"
else
    echo -e "${CYAN}Server will be available at:${NC}"
    echo "  http://localhost:$PORT"
fi

echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run Hugo server
# shellcheck disable=SC2086
exec hugo server $SERVE_FLAGS
