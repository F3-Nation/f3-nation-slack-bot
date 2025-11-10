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
ENV_FILE=".env"
SUBDOMAIN_VAR="LT_SUBDOMAIN_SUFFIX"
SUBDOMAIN_PREFIX="f3dev"

# Preflight checks for required CLIs
assert_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Required command not found: $1"; exit 1; }; }
assert_cmd lt
assert_cmd watchfiles
assert_cmd dotenv

ensure_subdomain_suffix() {
  local existing=""
  if [[ -f "${ENV_FILE}" ]] && grep -E "^${SUBDOMAIN_VAR}=" "${ENV_FILE}" >/dev/null; then
    existing=$(grep -E "^${SUBDOMAIN_VAR}=" "${ENV_FILE}" | tail -1 | cut -d= -f2-)
  fi
  if [[ -z "${existing}" ]]; then
    # Generate 6 hex chars (openssl preferred; fallback if unavailable)
    if command -v openssl >/dev/null 2>&1; then
      existing=$(openssl rand -hex 3)
    else
      existing=$(printf "%06x" $(( RANDOM * RANDOM )))
    fi
    # Add a newline if .env exists and does not end with one
    if [[ -f "${ENV_FILE}" ]] && [[ $(tail -c1 "${ENV_FILE}") != "" ]]; then
      echo >> "${ENV_FILE}"
    fi
    echo "${SUBDOMAIN_VAR}=${existing}" >> "${ENV_FILE}"
    echo "Generated and stored ${SUBDOMAIN_VAR}=${existing} in ${ENV_FILE}"
  fi
  LT_SUBDOMAIN="${SUBDOMAIN_PREFIX}-${existing}"
  export LT_SUBDOMAIN
}

generate_manifest() {
  local host="$1"
  echo "Generating app_manifest.json for host: ${host}"
  if [[ ! -f "${TEMPLATE_FILE}" ]]; then
    echo "Template file not found: ${TEMPLATE_FILE}"
    exit 1
  fi
  sed "s|HOST-PLACEHOLDER|${host}|g" "${TEMPLATE_FILE}" > app_manifest.json
  echo "Generated app_manifest.json with URL: ${host}"
}

start_lt() {
  ensure_subdomain_suffix
  : > "${LT_OUTPUT_FILE}"
  echo "Starting localtunnel on port 3000 with subdomain: ${LT_SUBDOMAIN}"
  ( lt --host http://loca.lt --port 3000 --subdomain "${LT_SUBDOMAIN}" > "${LT_OUTPUT_FILE}" 2>&1 ) &
  LT_PID=$!
  echo "localtunnel PID: ${LT_PID}"

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
    if grep -qi "subdomain.*taken" "${LT_OUTPUT_FILE}"; then
      echo "Requested subdomain already taken; regenerating suffix..."
      # Remove old suffix line, regenerate, restart
      sed -i "/^${SUBDOMAIN_VAR}=/d" "${ENV_FILE}" || true
      ensure_subdomain_suffix
      kill "${LT_PID}" 2>/dev/null || true
      ( lt --host http://loca.lt --port 3000 --subdomain "${LT_SUBDOMAIN}" > "${LT_OUTPUT_FILE}" 2>&1 ) &
      LT_PID=$!
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