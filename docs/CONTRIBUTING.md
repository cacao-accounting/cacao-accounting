# Colaborando con Cacao Accounting.

[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
![GitHub top language](https://img.shields.io/github/languages/top/cacao-accounting/cacao-accounting)
![GitHub language count](https://img.shields.io/github/languages/count/cacao-accounting/cacao-accounting)
![GitHub contributors](https://img.shields.io/github/contributors/cacao-accounting/cacao-accounting)
![GitHub last commit](https://img.shields.io/github/last-commit/cacao-accounting/cacao-accounting)
![GitHub issues](https://img.shields.io/github/issues/cacao-accounting/cacao-accounting)
![GitHub pull requests](https://img.shields.io/github/issues-pr-raw/cacao-accounting/cacao-accounting)


Gracias por su interes en colaborar con Cacao Accounting (el proyecto).

![Logo](https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/development/cacao_accounting/static/media/cacao_accounting%20_logo.png)

## Licencia del Proyecto.

Cacao Accounting es sofware libre y de código abierto liberado bajo la licencia Apache Versión 2 (la [licencia](https://github.com/cacao-accounting/cacao-accounting/blob/master/LICENSE) del proyecto), esto quiere decir que los usuarios del proyecto pueden:

* Usar el proyecto con o sin fines de lucro.
* Modificar el proyecto para ajustarlo a sus necesidades especificas (definiendo claramente los cambios realizados al proyecto original).

Sin embargo los usuarios no pueden:

* Hacer uso de las marcas registradas del proyecto
sin permiso explicito.
* Requerir garantias de cualquier tipo; el proyecto se distribuye tal cual sin garantias
de que pueda ser útil para algún fin especifico.

## Certifica el origen de tus aportes.

Para incorporar tus aportes al proyecto requerimos que certifiques que el o los aportes son de tu propiedad o que tienes permiso de terceros para incorporar el o los aportes al proyecto, siguiendo el [certificado de origen del desarrollador](https://developercertificate.org/).

Recomendamos ejecutar:

```bash
git commit -s
```

Y se agregara una firma apropiada al commit, no se incluiran en el proyecto commits sin el correspondiente
Sing-Off.

## Colaborando con el proyecto

### Formas de colaborar.

Pueden colaborar de distintas formas:

* Como desarrollador.
* Como control de Calidad (QA).
* [Escribiendo y mejorando la documentación](https://cacao-accounting.github.io/cacao-accounting/) o el [Manual de Usuario.](https://github.com/cacao-accounting/cacao-accounting-manual)
* [Aportando ideas de nuevas caracteristicas.](https://github.com/cacao-accounting/cacao-accounting/discussions)
* [Reportando errores.](https://github.com/cacao-accounting/cacao-accounting/issues)
* Traduciendo.
* Brindando guía y soporte a otros usuarios.
* Compartiendo el proyecto con otros.

Al formar de la comunidad del proyecto debes seguir el [código de conducta](CODE_OF_CONDUCT.md) establecido.

### Colaborando con el desarrollo del proyecto:

El desarrollo es multiplataforma, puedes utilizar tanto Windows, Linux o Mac
para aportar el proyecto, para colaborar con el proyecto necesitas:

  * [GIT](https://git-scm.com/)
  * [Yarn](https://yarnpkg.com/lang/en/)
  * [Python](https://www.python.org/downloads/)

La versión minima de Python soportada es: >=3.6

Tecnologías utilizadas:

* Backend: [Flask](https://flask.palletsprojects.com/en/1.1.x/).
* Frontend: [Bootstrap 5](https://v5.getbootstrap.com/).
* ORM: [SQLAlchemy](https://www.sqlalchemy.org/).

El desarrollo se realiza en la rama ```development```, una vez el proyecto sea liberado para producción
la rama ```main``` contendra la últma versión apta su uso en producción.

#### Obteniendo el codigo fuente:

Descarga el codigo fuente con:

```bash
git clone https://github.com/cacao-accounting/cacao-accounting.git
cd cacao-accounting
```

Para iniciar el proyecto es necesario seguir estos pasos:

#### Crear un entorno virtual de python.

```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate.bat
# Linux y MAC: 
source venv/bin/activate 
```

#### Instalar las dependencias:

```bash
python -m pip install -r requirements.txt
python -m pip install -r development.txt
python setup.py develop
yarn
```

Yarn es necesario para no tener que incluir librerias JavaScritp de terceros en el repositorio principal del proyecto.

Puede verificar que la instalación fue correcta ejecutando:

```bash
cacaoctl
Usage: python -m flask [OPTIONS] COMMAND [ARGS]...

  Interfaz de linea de comandos para la administración de Cacao Accounting.

Options:
  --version  Show the flask version
  --help     Show this message and exit.

Commands:
  activofijo
  cleandb     Elimina la base de datos, solo disponible para desarrollo.
  db          Perform database migrations.
  initdb      Crea el esquema de la base de datos.
  routes      Show the routes for the app.
  run         Run a development server.
  serve       Inicio la aplicacion con waitress como servidor WSGI por...
  shell       Run a shell in the app context.
  version     Muestra la version actual instalada.

```

#### Esquema de la base de datos

Para crear una base de datos de pruebas ejecutar:

```bash
cacaoctl initdb
```

#### Ejecutar servidor de desarrollo:

Para acceder al proyecto podemos utilizar el servidor web de desarrollo incluido en flask:

```bash
cacaoctl run
```

Para verficiar que el proyecto se ejecuta correctamente con un servidor WSGI acto para producción ejecutar:

```bash
cacaoctl serve
```

El usuario de pruebas es ```cacao``` con contraseña ```cacao```.

#### Guía de estilo:

Seguimos [PEP8](https://www.python.org/dev/peps/pep-0008/) con un largo de linea de 127 caracteres maximo.

[Black](https://github.com/psf/black) es una excelente herramienta para dar formato a tu código antes de hacer commit de tus cambios.

#### Pruebas automaticas:

Utilizamos [flake8](https://flake8.pycqa.org/en/latest/) y [pytest](https://docs.pytest.org/en/stable/) para asegurar la calidad del código fuente del proyecto.

Recomendamos ejecutar antes de enviar tus cambios:

```bash
black cacao_accounting
flake8 cacao_accounting
pytest
```

#### Escribe un buen mensaje en tu commit

Agracedemos te tomes tu tiempo para escribir un buen mensaje en tus commit, recomendamos seguir este ejemplo de [Chris Beams](https://chris.beams.io/posts/git-commit/):

```
Summarize changes in around 50 characters or less

More detailed explanatory text, if necessary. Wrap it to about 72
characters or so. In some contexts, the first line is treated as the
subject of the commit and the rest of the text as the body. The
blank line separating the summary from the body is critical (unless
you omit the body entirely); various tools like `log`, `shortlog`
and `rebase` can get confused if you run the two together.

Explain the problem that this commit is solving. Focus on why you
are making this change as opposed to how (the code explains that).
Are there side effects or other unintuitive consequences of this
change? Here's the place to explain them.

Further paragraphs come after blank lines.

 - Bullet points are okay, too

 - Typically a hyphen or asterisk is used for the bullet, preceded
   by a single space, with blank lines in between, but conventions
   vary here

If you use an issue tracker, put references to them at the bottom,
like this:

Resolves: #123
See also: #456, #789
```

Otros ejemplos de buenos mensajes de commit se pueden encontrar aca:

 - [Buenas Practicas En Commits De Git](https://www.codigofacilito.com/articulos/buenas-practicas-en-commits-de-git) 
 - [How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/)

#### Utilizar Commits Convencionales:

Solicitamos su apoyo para adoptar [Commits Convencionales](https://www.conventionalcommits.org/es/v1.0.0-beta.3/):


```
 - build: Cambios que efectan la distribución del proyecto.
 - ci: Actualización a herramientas para pruebas automaticas.
 - docs: Actualizacion de la documentación.
 - feat: Agrega funcionalidades nuevas.
 - fix: Correción de errores.
 - gui: Cambios que afectan la interfaz de usuario pero no la logica de negocios.
 - refactor: Modificaciones que no agregan nuevas funciones o arreglan errores.
 - style: Correcciones de Estilo.
 - test: Cambios en pruebas unitarios.
```

Independientemente del tipo un commit con el texto BREAKING CHANGE, sin importar su tipo, se traducen a un cambio de versión MAJOR.

#### Versionado semantico

Para Cacao Accounting hemos adoptado [versiones semanticas](https://www.conventionalcommits.org/en/v1.0.0/).

Mayor: Al ser una aplicación contable trabajamos con datos historicos, así que cualquier cambio en
la estructura de base datos que agregue cambios no compatibles con versiones anteriores se debera considerar un cambio mayor y requerir un lanzamiento mayor. Una migración efectiva del esquema de la
base de datos debe proveerse a los usuarios.

Menor: Lanzamiento de nuevas caracteristicas.

Path: Correciones menores.

Fix: Correción de errores criticos.

#### Ejecutar pruebas unitarias:

```bash
export CACAOTEST=True
pytest
```

##### Configurar Base de datos para pruebas

El proyecto se prueba con SQLite, MySQL 8, Postgresql 13 y MS SQL Server.

###### MySQL

Para crear una base de datos de pruebas ejecutar los siguientes queries en MySQL:

```sql
CREATE DATABASE IF NOT EXISTS cacao;
CREATE USER IF NOT EXISTS 'cacao' IDENTIFIED BY 'cacao';
GRANT ALL PRIVILEGES ON cacao.* TO 'cacao';
FLUSH PRIVILEGES;
```

###### Postgresql

Para crear una base de datos de pruebas ejecutar los siguientes queries en Postgresql:

```sql
CREATE DATABASE cacao;
CREATE USER cacao WITH PASSWORD 'cacao';
GRANT ALL PRIVILEGES ON DATABASE cacao TO cacao;
```

###### Pruebas de integración 

Para vaidar que las vases de datos fueron creadas correctamente y la conexión es correcta ejecutar:

```bash
python tests\database.py
MySQL disponible
Postgresql disponible
```

Para ejecutar las pruebas ejecutar:

```bash
pytest tests\database.py
```

#### Empaquetar para distribución:

Para crear los archivos para distribuir el proyecto ejecutar:

```bash
python -m build
twine check dist/*
# Solo usuario con permisos de cargar en Pypi.
twine upload dist/*
```

Es un objetivo principal que el proyecto sea [pip instalable](https://pypi.org/project/cacao-accounting/) así como ofrecer una versión del proyecto que pueda ser utilizada como [aplicación de escritorio](https://pypi.org/project/cacao-accounting-desktop/), para cumplir este objetivo hemos desarrollado [open marquesote](https://pypi.org/project/open-marquesote/).


### Varios

Estos son algunos tips a tomar en cuenta opcionalmente

#### Ignorar correcciones de estilo en git blame

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```
