
## Setup the Cacao Accounting service with systemd.

In most Linux systems systemd is the default init system, with systemd you can setup a
autostart service to start Cacao Accounting on system boot. You will create a `.unit` file
to configure a system service.

!!! note

    If you follow the instructions to install Cacao Accounting from [sources](py_sources.md) or from
    the [Python Package Index](py_pypi.md) the `cacaoctl` tool should be instaled and available in
    `/opt/cacao-accounting/venv/bin/cacaoctl`.

!!! tip

    You must configure and initialice the database for Cacao Accounting, you can shoose the database
    server you prefer [PostgreSQL](py_database_psql.md) or [MySQL](py_database_mysql.md), you will need
    the connections string to configure your database service as a enviroment variable in the `.unit` file.

### Example `.unit` file.

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
ExecStart=/opt/cacao-accounting/venv/bin/cacaoctl serve

[Install]
WantedBy=multi-user.target
```

Save the file in `/etc/systemd/system/cacao-accounting.service`

!!! note

    Cacao Accounting requires at less two required configuration options to run `CACAO_DB` and `CACAO_KEY`
    to run, you can read more about available configuration options in [the configuration page](set_up.md)
    also you can find examples of the correct connection string format according to the database service you
    are using.

### Reload the systemd daemon and start the Cacao Accounting service.

Once you have configured your Cacao Accounting `.unit` file you can start the service with

```bash
sudo systemctl daemon-reload
sudo systemctl enable cacao-accounting.service --now
sudo systemctl status cacao-accounting.service
```

Once configured your Cacao Accounting service you can visit `<your_ip_address>:8080` and access the
Cacao Accounting loggin screen, you can loggin with the administrator user and password and follow the
initial setup wizard.

!!! note

    For small setups with a few users (<= 2 users) this setup should work, but you are sposing
    the built in wsgi server to the internet, this is not the recommend setup if your are going to serve
    many users.

You can configure a web server to ensure your setup and do not spoce your wsgi server to the internet like
nginx and Caddy Server, in the next step we will configure [Caddy as reverse proxy](py_server.md).