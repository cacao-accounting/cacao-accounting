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

Recomendamos utilizar [Libre Office Calc](https://es.libreoffice.org/descubre/calc/) para editar los
archivos ya que proporciona una exportación mas limpia de los archivos .csv, MS Excel suele exportar
los documentos utilizando ";" como separador el sistema espera "," como separador, es opcional el uso
de comillas (") como separadores de columan pero es recomendable.

