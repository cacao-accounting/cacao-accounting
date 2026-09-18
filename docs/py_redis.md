# Setup a Redis service.

=== ":simple-ubuntu: APT Based OS"

    ``` bash
    sudo apt update
    sudo apt install -y redis-server
    sudo systemctl enable redis-server.service --now
    ```

=== ":simple-fedora: RPM Based OS"

    ```bash
    sudo dnf update
    sudo dnf install -y redis
    sudo systemctl enable redis.service --now
    ```

Once Redis is available, update your [systemd unit service](py_systemd.md) with separate
Redis URLs: `CACHE_REDIS_URL` points to database 2 for application cache, and
`RATELIMIT_STORAGE_URI` points to database 0 for rate limiting:

```
[Unit]
Description=Cacao Accounting service.
After=syslog.target network.target

[Service]
Type=simple
Restart=on-failure
RestartSec=5
Environment="CACAO_KEY=hajkañdkjda455654ASSDAFCAFADASDÑÑÑÑÑÑññññññlkadjasdkldaldkd"
Environment="CACAO_DB=protocol+driver://user:password@host:port/dbname"
Environment="CACHE_REDIS_URL=redis://localhost:6379/2"
Environment="RATELIMIT_STORAGE_URI=redis://localhost:6379/0"
ExecStart=/opt/cacao-accounting/venv/bin/cacaoctl serve

[Install]
WantedBy=multi-user.target
```
