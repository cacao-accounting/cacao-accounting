podman pod create --name cacao-mysql -p 9980:80 -p 9443:443 -p 9443:443/udp

podman volume create cacao-mysql-backup

podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-db \
    --volume cacao-mysql-backup:/var/lib/mysql  \
    -e MYSQL_ROOT_PASSWORD=cacaodb \
    -e MYSQL_DATABASE=cacaodb \
    -e MYSQL_USER=cacaodb \
    -e MYSQL_PASSWORD=cacaodb \
    -d docker.io/library/mysql:8

podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-server \
    -v ./Caddyfile:/etc/caddy/Caddyfile:z \
    -v caddy_data:/data \
    -v caddy_config:/config \
    -d docker.io/library/caddy:alpine

podman run --pod cacao-psql --rm --replace --init --name cacao-mysql-cache \
-d docker.io/library/valkey:alpine

podman run --pod cacao-mysql --rm --replace --init --name cacao-mysql-app \
    -e CACAO_KEY=nsjksAAA.ldknsdlkd532445yryrgfhdyyreysljdn \
    -e CACAO_DB=mysql+pymysql://cacaodb:cacaodb@localhost:3306/cacaodb \
    -e CACAO_USER=cacaouser \
    -e CACAO_PSWD=cacaopwd \
    -e CACHE_REDIS_URL=redis:localhost:6379/1 \
    -d quay.io/cacaoaccounting/cacaoaccounting:main
