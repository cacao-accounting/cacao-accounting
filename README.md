# Cacao Accounting

Aplicacion contable para micro, pequeñas y medianas empresas (MiPymes).

:warning:  
* Este es un proyecto en etapa temprana de desarrollo.
* No apta para uso en producción.


## Participar en el Proyecto:

Todos los aportes son bienvenidos.

### Requisitos para el desarrollo:

  * [GIT](https://git-scm.com/)
  * [Nodejs](https://nodejs.org/en/)
  * [Yarn](https://yarnpkg.com/lang/en/)
  * [Python](https://www.python.org/downloads/)

El desarrollo es multiplataforma, puedes utilizar tanto Windows, Linux o Mac
para aportar el proyecto.

#### Obteniendo el codigo fuente:

Descarga el codigo fuente con:

```bash
git clone https://github.com/cacao-accounting/cacao-accounting-mockup.git
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
# Python
  python -m pip install -r requirements.txt

# Nodejs
  yarn
```

Yarn es necesario para no tener incluir librerias de JavaScritp de terceros en el repositorio principal del proyecto.

#### Esquema de la base de datos

Para crear una base de datos sqlite de pruebas ejecutar:

```bash
  flask init-db
```

#### Ejecutar servidor de desarrollo:

Para acceder al proyecto podemos utilizar el servidor web de desarrollo incluido en flask:

```bash
  python setup.py develop
  flask run
```
# Licencia.

Derechos de autor 2020 William José Moreno Reyes

Autorizado en virtud de la Licencia de Apache, Versión 2.0 (la "Licencia"); se
prohíbe utilizar este archivo excepto en cumplimiento de la Licencia. Podrá
obtener una copia de la Licencia en:

  http://www.apache.org/licenses/LICENSE-2.0

A menos que lo exijan las leyes pertinentes o se haya establecido por escrito,
el software distribuido en virtud de la Licencia se distribuye “TAL CUAL”, SIN
GARANTÍAS NI CONDICIONES DE NINGÚN TIPO, ya sean expresas o implícitas. Véase
la Licencia para consultar el texto específico relativo a los permisos y
limitaciones establecidos en la Licencia.
