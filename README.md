# cacao-accounting-mockup

Requisitos:

  * Nodejs 12 o superior
  * Yarn 1.12 o superior
  * Python 3.7 o superior

  Este en un simple proyecto en Flask utilizando la funcion render_template() para mostrar en el navegador 
  plantillas utilizando Jinja2 como motor de renderizado.

## Iniciando proyecto:

```bash
git clone https://github.com/cacao-accounting/cacao-accounting-mockup.git
```

Para iniciar el proyecto es necesario seguir estos pasos:

### Crear un entorno virtual de python.

```bash
  python -m venv venv
  venv\Scripts\activate.bat
```

### Instalar las dependencias:

```bash
# Python
  python -m pip install -r requirements.txt

# Nodejs
  yarn
```

## Iniciar

Para acceder al proyecto podemos utilizar el servidor web de desarrollo incluido en flask:

```bash
  python setup.py develop
  python wsgi.py    
```
