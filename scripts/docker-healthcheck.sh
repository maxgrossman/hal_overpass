#!/bin/bash
set -uef -o pipefail

/usr/bin/curl \
    -o /dev/null -f \
    http://${HAL_HOST:-0.0.0.0}:${HAL_PORT:-8080}/ping