
## Uso de un proxy inverso

Cacao Accounting utiliza [waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/index.html) como servidor WSGI por defecto, las razones por la que se seleccion
como servidor Waitress son:

 - Es una implementación en 100% Python
 - Funciona tanto en Windows como en Linux
 - Presenta un desempeño aceptable

Si bien no se recomienda exponer al servidor WSGI a la Internet, este articulo en ingles explica con bastante detalle porque no se debe exponer un servidor WSGI a la internet: https://rushter.com/blog/gunicorn-and-low-and-slow-attacks/

### Utilizando NGINX como servidor proxy

NGINX es un popular servidor web de código abierto que suele utilizarse como servidor proxy.

#### Ubuntu 

Para utilizar NGINX como proxy inverso en Ubuntu utilizar:

```
sudo apt update
sudo apt install nginx
sudo ufw allow 'Nginx HTTPS'
```

Debe crear el archivo de configuración en:

```
sudo vi /etc/nginx/sites-available/cacao
```

Y agregue el siguiente contenido:

```
server {
    listen 8443;
    server_name cacao;

location / {
  include proxy_params;
  proxy_set_header Host $host;
  proxy_pass proxy_pass http:s//127.0.0.1:8000;
    }
}
```

Ejecute:

```
sudo systemctl restart nginx
```
