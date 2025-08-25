param(
  [string]$Image="vision2509/warehouse:1.0.0",
  [int]$HostPort=8001
)

docker stop warehouse 2>$null | Out-Null
docker rm warehouse 2>$null | Out-Null

docker run -d --name warehouse `
  -p $HostPort`:8000 `
  -e DJANGO_SECRET_KEY=change_me `
  -e DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost" `
  -e DJANGO_DEBUG=False `
  -e DJANGO_CSRF_TRUSTED_ORIGINS="http://localhost:$HostPort" `
  -e COLLECT_STATIC=1 `
  -v "${PWD}\.docker-data\db.sqlite3:/app/db.sqlite3" `
  -v "${PWD}\.docker-data\media:/app/media" `
  $Image

docker logs -f warehouse
