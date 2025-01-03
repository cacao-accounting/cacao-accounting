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

Once Redis is available you can update your [systemd unit service](py_systemd.md) with
the new enviromet variable `CACHE_REDIS_URL` pointing to `redis://localhost:6379/1`:

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
Environment="CACHE_REDIS_URL= redis://localhost:6379/1"
ExecStart=/opt/cacao-accounting/venv/bin/cacaoctl serve

[Install]
WantedBy=multi-user.target
```