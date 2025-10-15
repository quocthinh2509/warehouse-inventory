#!/usr/bin/env sh
set -e

# python manage.py migrate --noinput

# Thu gom static ở runtime nếu muốn
if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
