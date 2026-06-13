#!/bin/bash
set -e

wait_for_port() {
  local host="$1" port="$2"
  echo "Waiting for $host:$port..."
  until timeout 1 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; do
    sleep 1
  done
  echo "$host:$port ready."
}

wait_for_port postgres 5432

exec process-opt-api