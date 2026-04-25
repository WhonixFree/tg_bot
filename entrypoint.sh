#!/usr/bin/env sh
set -eu

APP_DIR="/app"
ALEMBIC_CONFIG="${ALEMBIC_CONFIG:-/app/alembic.ini}"

require_env() {
    var_name="$1"
    eval "var_value=\${$var_name:-}"
    if [ -z "$var_value" ]; then
        echo "$var_name is required." >&2
        exit 1
    fi
}

require_env DATABASE_URL

if [ ! -f "$ALEMBIC_CONFIG" ]; then
    echo "Alembic config not found at $ALEMBIC_CONFIG." >&2
    exit 1
fi

if [ ! -f "${APP_DIR}/alembic/env.py" ]; then
    echo "Alembic env.py not found at ${APP_DIR}/alembic/env.py." >&2
    exit 1
fi

cd "$APP_DIR"

wait_for_migrations() {
    attempt=1
    max_attempts="${DB_MIGRATION_MAX_ATTEMPTS:-20}"
    sleep_seconds="${DB_MIGRATION_RETRY_DELAY_SECONDS:-3}"

    while [ "$attempt" -le "$max_attempts" ]; do
        if alembic -c "$ALEMBIC_CONFIG" upgrade head; then
            return 0
        fi

        if [ "$attempt" -lt "$max_attempts" ]; then
            echo "Migration attempt ${attempt} failed. Waiting for database..." >&2
            sleep "$sleep_seconds"
        fi

        attempt=$((attempt + 1))
    done

    echo "Database migrations failed after ${max_attempts} attempts." >&2
    return 1
}

wait_for_migrations

PAYMENT_PROVIDER_MODE="${PAYMENT_PROVIDER_MODE:-mock}"

if [ "$PAYMENT_PROVIDER_MODE" != "live" ]; then
    exec "$@"
fi

require_env APP_BASE_URL
require_env PAYMENT_WEBHOOK_PATH
require_env PAYMENT_WEBHOOK_REGISTER_URL
require_env MERCHANT_API_KEY
require_env MERCHANT_PROJECT_UUID

APP_BASE_URL="$(printf '%s' "$APP_BASE_URL" | sed 's#/*$##')"
PAYMENT_WEBHOOK_REGISTER_URL="$(printf '%s' "$PAYMENT_WEBHOOK_REGISTER_URL" | sed 's#/*$##')"

case "$APP_BASE_URL" in
    http://*|https://*) ;;
    *)
        echo "APP_BASE_URL must start with http:// or https://." >&2
        exit 1
        ;;
esac

case "$PAYMENT_WEBHOOK_PATH" in
    /*) ;;
    *)
        echo "PAYMENT_WEBHOOK_PATH must start with /." >&2
        exit 1
        ;;
esac

FULL_WEBHOOK_URL="${APP_BASE_URL}${PAYMENT_WEBHOOK_PATH}"
export APP_BASE_URL PAYMENT_WEBHOOK_PATH FULL_WEBHOOK_URL

build_signature() {
    printf '%s' "$1" | python -c 'import base64, hashlib, hmac, os, sys; body = sys.stdin.buffer.read(); print(hmac.new(os.environ["MERCHANT_API_KEY"].encode("utf-8"), base64.b64encode(body), hashlib.sha256).hexdigest())'
}

register_webhook() {
    payload="$(printf '{"url_callback":"%s"}' "$FULL_WEBHOOK_URL")"
    signature="$(build_signature "$payload")"

    if [ -n "${MERCHANT_PROJECT_UUID:-}" ]; then
        curl --silent --show-error --fail-with-body \
            --request POST \
            --header "Content-Type: application/json" \
            --header "project: ${MERCHANT_PROJECT_UUID}" \
            --header "sign: ${signature}" \
            --data "$payload" \
            "$PAYMENT_WEBHOOK_REGISTER_URL"
    else
        curl --silent --show-error --fail-with-body \
            --request POST \
            --header "Content-Type: application/json" \
            --header "sign: ${signature}" \
            --data "$payload" \
            "$PAYMENT_WEBHOOK_REGISTER_URL"
    fi
}

attempt=1
while [ "$attempt" -le 3 ]; do
    if register_webhook; then
        exec "$@"
    fi

    if [ "$attempt" -lt 3 ]; then
        echo "Webhook registration attempt ${attempt} failed. Retrying..." >&2
        sleep 2
    fi

    attempt=$((attempt + 1))
done

echo "Webhook registration failed after 3 attempts." >&2
exit 1
