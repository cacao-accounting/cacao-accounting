# cacao-accounting-mockup

Requisitos:

  * [Nodejs](https://nodejs.org/en/) 12 o superior
  * [Yarn](https://yarnpkg.com/lang/en/) 1.12 o superior
  * [Python](https://www.python.org/downloads/) 3.8 o superior

  Este en un simple proyecto en Flask utilizando la funcion render_template() para mostrar en el navegador 
  plantillas utilizando Jinja2 como motor de renderizado.

## Iniciando proyecto:

Descarga el codigo fuente con:

```bash
git clone https://github.com/cacao-accounting/cacao-accounting-mockup.git
```

Para iniciar el proyecto es necesario seguir estos pasos:

### Crear un entorno virtual de python.

```bash
  python -m venv venv
  venv\Scripts\activate.bat # Windows
  source venv/bin/activate # Linux
```

### Instalar las dependencias:

```bash
# Python
  python -m pip install -r requirements.txt

# Nodejs
  yarn
```

Yarn es necesario para no tener incluir librerias de JavaScritp de terceros en el repositorio principal del proyecto.

## Iniciar

Para acceder al proyecto podemos utilizar el servidor web de desarrollo incluido en flask:

```bash
  python setup.py develop
  flask run
```
