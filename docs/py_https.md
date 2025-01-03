# Setup a SSL certificate.

The Caddy server, will setup a automatic SSL certificate in most cases, to have a valid SSL
certificate you will need a [`domain name`](https://en.wikipedia.org/wiki/Domain_Name_System)
pointing to your server `ip` with a `A` or `AAA` DNS record.

With a DNS record pointing to your server IP you can use the[automatic https](https://caddyserver.com/docs/automatic-https)
feature of the Caddy web server, for this you must update your Caddyfile in `/etc/caddy/Caddyfile`
to list your domain name like this:

```
example.com, www.example.com {
	...
}
```
