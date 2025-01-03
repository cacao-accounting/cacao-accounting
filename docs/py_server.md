
# Setup a reverse proxy server

In this step we will seutp Caddy as a proxy server, install Caddy Server with:

=== ":simple-ubuntu: APT Based OS"

    ``` bash
    sudo curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    sudo curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt update
    sudo apt install -y caddy
    sudo ufw allow 80
    sudo ufw allow 443
    sudo ufw reload
    sudo systemctl enable caddy --now
    ```

=== ":simple-fedora: RPM Based OS"

    ```bash
    sudo dnf install -y 'dnf-command(copr)'
    sudo dnf copr enable @caddy/caddy
    sudo dnf install -y caddy
    sudo firewall-cmd --permanent --zone=public --add-service=http
    sudo firewall-cmd --permanent --zone=public --add-service=https
    sudo firewall-cmd --reload
    sudo systemctl enable caddy --now
    ```

Once installed Caddy will create the configuration file in `/etc/caddy/Caddyfile`, you can configure Caddy
as reverse proxy with the following configuration:

```
:80 {
  reverse_proxy localhost:8080
}
```

With this setup the server server will recibe the request and past then to the wsgi in the backgroud.
