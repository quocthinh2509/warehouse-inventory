# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Tối ưu cache: copy requirements trước nếu có
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    if [ -f /tmp/requirements.txt ]; then pip install -r /tmp/requirements.txt; fi && \
    pip install gunicorn whitenoise && pip install djangorestframework django-cors-headers djangorestframework-simplejwt
    # chuyen  het sang requirement.txt

# Copy toàn bộ source
COPY . /app

# (tuỳ chọn) collectstatic lúc build (không bắt buộc)
ARG COLLECT_STATIC=0
RUN if [ "$COLLECT_STATIC" = "1" ]; then \
      python manage.py collectstatic --noinput || true ; \
    fi

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Tạo user thường
RUN groupadd -r app && useradd -r -g app app && chown -R app:app /app
USER app

EXPOSE 8000

ENV DJANGO_DEBUG=False \
    PORT=8000


ENTRYPOINT ["/entrypoint.sh"]

# CHÍNH XÁC CHO DỰ ÁN CỦA BẠN:
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "warehouse.wsgi:application"]
