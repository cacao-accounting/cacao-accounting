podman pod create --name cacao-psql -p 9981:80 -p 9444:443 -p 9444:443/udp

podman volume create cacao-postgresql-backup

podman run --pod cacao-psql --rm --name cacao-psql-db \
    --volume cacao-postgresql-backup:/var/lib/postgresql/data \
    -e POSTGRES_DB=cacaodb \
    -e POSTGRES_USER=cacaodb \
    -e POSTGRES_PASSWORD=cacaodb \
    -d docker.io/library/postgres:17-alpine

podman run --pod cacao-psql --rm --replace --init --name cacao-psql-server \
    -v ./Caddyfile:/etc/caddy/Caddyfile:z \
    -v caddy_data:/data \
    -v caddy_config:/config \
    -d docker.io/library/caddy:alpine

podman run --pod cacao-psql --rm --init --name cacao-psql-app \
    -e CACAO_KEY=nsjksldknsdlkdsljasfsadggfhhhhf5325364dn \
    -e CACAO_DB=postgresql+pg8000://cacaodb:cacaodb@localhost:5432/cacaodb \
    -e CACAO_USER=cacaouser \
    -e CACAO_PWD=cacappwd \
    -d quay.io/cacaoaccounting/cacaoaccounting
