#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Sử dụng: $0 [server_address]"
    echo "Ví dụ: $0 user@example.com"
    exit 1
fi

SERVER_ADDRESS=$1

# Upload toàn bộ folder warehouse lên server bằng rsync
echo "Upload toàn bộ folder warehouse lên server..."
rsync -avz --progress ./ $SERVER_ADDRESS:/var/www/warehouse/

# SSH vào server để deploy container
ssh $SERVER_ADDRESS bash -s <<'ENDSSH'
# Kiểm tra nếu container 'warehouse' đang chạy
if [ $(docker ps -q -f name=warehouse) ]; then
    echo "Dừng container cũ..."
    docker stop warehouse
fi

# Kiểm tra nếu container 'warehouse' tồn tại (ngay cả khi không chạy)
if [ $(docker ps -aq -f name=warehouse) ]; then
    echo "Xóa container cũ..."
    docker rm warehouse
fi

# Chạy container mới với auto restart
echo "Chạy container mới..."
docker run -d \
  -p 8000:8000 \
  --name warehouse \
  --user root \
  --restart unless-stopped \
  -v /var/www/warehouse:/app \
  vision2509/warehouse:latest
ENDSSH
