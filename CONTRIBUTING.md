# Colaborando con Cacao Accounting.

Gracias por su interes en colaborar con Cacao Accounting (el proyecto).

## Licencia del Proyecto.

Cacao Accounting es sofware libre y de código abierto liberado bajo la licencia Apache Versión 2 (la [licencia](https://github.com/cacao-accounting/cacao-accounting/blob/master/LICENSE) del proyecto), esto quiere decir que los usuarios del proyecto pueden:

* Usar el proyecto con o sin fines de lucro.
* Modificar el proyecto para ajustarse a sus necesidades especificas (definiendo claramente los cambios realizados al proyecto original).

Sin embargo los usuarios no pueden:

* Hacer uso de las marcas registradas del proyecto
sin permiso explicito.
* Requerir garantias de cualquier tipo; el proyecto se distribuye tal cual sin garantias
de que pueda ser útil para algún fin especifico.

## Certifica el origen de tus aportes.

Para incorporar tus aportes al proyecto requerimos que certifiques el o los aportes son de tu propiedad o que tienes permiso de terceros para incorporar el aporte al proyecto, siguiendo el [certificado de origen del desarrollador](https://developercertificate.org/).

Recomendamos ejecutar:

```bash
git commit -s
```

Y se agregara una firma apropiada al commit.

## Colaborando con el proyecto

### Formas de colaborar.

Pueden colaborar de distintas formas:

* Como desarrollador.
* Escribiendo documentación.
* Aportando ideas de nuevas caracteristicas.
* Reportando errores.
* Traduciendo.
* Brindando guía y soporte a otros usuarios.
* Compartiendo el proyecto con otros.

Al formar de la comunidad del proyecto debes seguir el [código de conducta](https://github.com/cacao-accounting/cacao-accounting/blob/master/CODE_OF_CONDUCT.md) establecido.

### Colaborando con el desarrollo del proyecto:

El desarrollo es multiplataforma, puedes utilizar tanto Windows, Linux o Mac
para aportar el proyecto, para colaborar con el proyecto necesitas:

  * [GIT](https://git-scm.com/)
  * [Nodejs](https://nodejs.org/en/)
  * [Yarn](https://yarnpkg.com/lang/en/)
  * [Python](https://www.python.org/downloads/)

Tecnologías utilizadas:
* Backend: [Flask](https://flask.palletsprojects.com/en/1.1.x/)
* Frontend: [PatternFly](https://www.patternfly.org/v4/)
* ORM: [SQLAlchemy](https://www.sqlalchemy.org/), con soporte a Postgresql, Mysql y Sqlite (Mariadb hasta que tenga soporte real a [JSON](https://mariadb.com/kb/en/json-data-type/))

El desarrollo se realiza en la rama development.

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
.\venv\Scripts\activate.bat # Windows
source venv/bin/activate # Linux
```

#### Instalar las dependencias:

```bash
python -m pip install -r requirements.txt
python setup.py develop
yarn
```

Yarn es necesario para no tener que incluir librerias JavaScritp de terceros en el repositorio principal del proyecto.

#### Esquema de la base de datos

Para crear una base de datos de pruebas ejecutar:

```bash
flask init-db
flask demo-data
```

#### Ejecutar servidor de desarrollo:

Para acceder al proyecto podemos utilizar el servidor web de desarrollo incluido en flask:

```bash
flask run
```

Para verficiar que el proyecto se ejecuta correctamente con un servidor WSGI acto para producción ejecutar:

```bash
python wsgi.py
```

El usuario de pruebas es cacao con contraseña cacao.

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

#### Empaquetar para distribución:

Para crear el tarball y wheel del proyecto ejecutar:

```bash
python -m pep517.build .
```
