# Catalogos de Cuentas para Cacao Accounting

Para facilitar que los archivos de catalogos de cuentas puedan ser editados facilmente por
personal contable utilizamos archivos separados por comas (.csv) para los archivos base de 
los catalogos contables.

El archivo debe tener el siguiente contenido:

 - codigo: Código numerico unico que identifica la cuenta a nivel de usuario.
 - nombre: Cadena de texto que describe el uso de la cuenta contable.
 - padre: La estructura padre/hijo es la base del arbol de cuentas, debe ser grupo=1. 
 - grupo: Uno de 1 o 0, 1 significa que la cuenta es un agrupador, 0 indica que la cuenta acepta movimiento.
 - rubro: Uno de Asset, Liability, Equity, Income, Expense, Memo.
 - tipo: 

## Opciones para la presentación alternativa:


### Codificación Alternativa

Es común que la información financiera de una entidad deba prepararse para distintos usuarios que tienen distintas necesidades, por ejemplo el Cátalogo Contable puede estar extructura de acuerdo a las necesidades de la gerencia pero la entidad puede tener que preparar reportes para otras entidades como los bancos que no
requieren tanto nivel de detalle.

Para abordar este escenario Cacao Accounting permite que el usuario establesca una numeración alternativa, que permite presentar los reportes en una estructura distinta sin tener que refurmular la estructura del Catálogo de Cuentas Contables.

La logica es:

1. Solo las cuentas de tipo grupo 1 se consideran en la presentación alternativa
2. Si una cuenta no tiene no tiene cuenta alternativa definida se presentara tal cual esta definida
3. Las cuentas hijo de una padre heredan su cuenta alternativa.
4. Para definir si una cuenta tiene una presentación alternativa el catalogo de cuentas se escanea desde las cuentas raiz hacía abajo.
5. Varias cuentas pueden tener la misma presentación alternativa, el sistema las va a sumar bajo un mismo registro.

### Codificación Fiscal

Similar a la logica de presentación alternativa las autoridades fiscales suelen requerir la presentación de la información de la entidad de una forma predeterminada la cual suele ser bastante rigida, a diferencia de la cuenta para presentación alternativa la cuenta para la presentación fiscal se debe establecer en las cuentas a nivel de detalle, es decir de tipo grupo 0.

Esto se define así para poder identificar individualmente las cuentas que se incluyen en un determinado tratamiento fiscal, el ejemplo mas facil de esta clasificación es dividir los ingresos entre gravables y no gravables o los gastos entre deducibles y no deducibles. Los formatos fiscales suelen estar numerados, recomendamos usar los reglones de los reportes fiscales como codificación alternativa.

 ## Proponer un nuevo Catálogo de Cuentas 

Recomendamos utilizar [Libre Office Calc](https://es.libreoffice.org/descubre/calc/) para editar los
archivos ya que proporciona una exportación mas limpia de los archivos .csv, MS Excel suele exportar
los documentos utilizando ";" como separador el sistema espera "," como separador, es opcional el uso
de comillas (") como separadores de columan pero es recomendable.

