#!/bin/bash
# Chạy Redis trong Docker với password

docker run -d \
  --restart always \
  --name redis_server \
  -p 6379:6379 \
  -e REDIS_PASSWORD='The20@12345' \
  redis:7.2-alpine \
  redis-server --requirepass 'The20@12345'
