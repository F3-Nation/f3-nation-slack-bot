#!/bin/bash
# filepath: /app/app_startup.sh

set -Eeu -o pipefail

# Simple supervisor that keeps both the local server and localtunnel running.
# - Starts localtunnel, captures its URL, and (re)generates app_manifest.json
# - Starts the app with watchfiles and restarts either process if it exits

LT_OUTPUT_FILE="lt_output.txt"
LT_PID=""
APP_PID=""
LT_HOST=""
STOPPING=false
TEMPLATE_FILE="app_manifest.template.json"

# Preflight checks for required CLIs
assert_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Required command not found: $1"; exit 1; }; }
assert_cmd lt
assert_cmd watchfiles
assert_cmd dotenv

generate_manifest() {
  local host="$1"
  echo "Generating app_manifest.json for host: ${host}"
  if [[ ! -f "${TEMPLATE_FILE}" ]]; then
    echo "Template file not found: ${TEMPLATE_FILE}"
    exit 1
  fi
  # Substitute HOST-PLACEHOLDER token with the resolved host
  sed "s|HOST-PLACEHOLDER|${host}|g" "${TEMPLATE_FILE}" > app_manifest.json
  echo "Generated app_manifest.json with URL: ${host}"
}

start_lt() {
  # Start localtunnel in the background and capture output
  : > "${LT_OUTPUT_FILE}"
  echo "Starting localtunnel on port 3000..."
  ( lt --port 3000 > "${LT_OUTPUT_FILE}" 2>&1 ) &
  LT_PID=$!
  echo "localtunnel PID: ${LT_PID}"

  # Wait for the tunnel to provide a URL or error (timeout ~30s)
  for _ in {1..60}; do
    if grep -q "your url is:" "${LT_OUTPUT_FILE}"; then
      local url
      url=$(grep -m1 "your url is:" "${LT_OUTPUT_FILE}" | awk '{print $4}')
      local host
      host=$(echo "$url" | sed -E 's|https?://([^/]+).*|\1|')
      echo "Localtunnel URL: $url"
      if [[ -z "${LT_HOST}" || "${LT_HOST}" != "$host" ]]; then
        LT_HOST="$host"
        generate_manifest "$LT_HOST"
      fi
      break
    fi
    if grep -q "Error:" "${LT_OUTPUT_FILE}"; then
      echo "localtunnel reported an error (will retry if it exits):"
      tail -n +1 "${LT_OUTPUT_FILE}" | sed 's/^/LT: /' || true
      break
    fi
    sleep 0.5
  done
}

start_app() {
  echo "Starting the app with watchfiles..."
  ( watchfiles --filter python 'dotenv -f .env run -- python main.py' ) &
  APP_PID=$!
  echo "App PID: ${APP_PID}"
}

cleanup() {
  echo "Shutting down processes..."
  if [[ -n "${LT_PID:-}" ]] && kill -0 "${LT_PID}" 2>/dev/null; then
    kill "${LT_PID}" 2>/dev/null || true
  fi
  if [[ -n "${APP_PID:-}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    kill "${APP_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
# On SIGINT/SIGTERM, mark stopping, cleanup, and exit
trap 'STOPPING=true; cleanup; exit 0' SIGINT SIGTERM
# Always cleanup on script exit as a safety net
trap cleanup EXIT

# Initial start
start_lt
start_app

# Supervision loop: restart whichever process exits; regenerate manifest if URL changes
while true; do
  # Wait for any child to exit
  if ! wait -n "${LT_PID}" "${APP_PID}"; then
    : # ignore child exit status; we'll restart below
  fi

  # If we're stopping, break out without restarting
  if [[ "$STOPPING" == true ]]; then
    break
  fi

  # Restart whichever died
  if ! kill -0 "${LT_PID}" 2>/dev/null; then
    echo "localtunnel exited; restarting..."
    start_lt
  fi
  if ! kill -0 "${APP_PID}" 2>/dev/null; then
    echo "App process exited; restarting..."
    start_app
  fi
done