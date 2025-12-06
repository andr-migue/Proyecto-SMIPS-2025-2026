Pasos para incorporar:
1- Copiar el contenido a la carpeta de su proyecto
2- Sobrescribir (si usan VSC, revisen que no se pierda nada importante en settings.json)

Que trae?

1- Soporte para Windows
Para correr los tests, hay que ejecutar un comando similar al original:

Ej:
./test.py tests s-mips.circ -o ./tests-out s-mips-template.circ -p py -l C:/logisim-win-2.7.1.exe

Tiene dos parametros nuevos:
-p %python command%: especificar comando para llamar a python, usualmente py en Windows.
-l %logisim.exe path%: especificar la ruta al ejecutable de Logisim. Si se coloca Logisim
en la carpeta del proyecto, es tan simple como escribir "Logisim.exe" e ignorar la ruta.

2- Soporte para Unittest (y VSC)
El archivo test.py ahora Tambien implementa unittest para generar los casos de prueba.
Esto no quiere decir que no se pueda seguir usando de la forma anterior. Para correrlos
(en VSC, si usa otro IDE, corre por su cuenta):

- Abrir la seccion "Testing" de la barra lateral
- Si no se muestran los tests:
    - Asegurese de haber copiado el nuevo archivo test.py a su proyecto
    - Asegurese de haber copiado el contenido del archivo /.vscode/settings.json a su proyecto
    - Abra el archivo test.py en VSC
- IMPORTANTE: Configurar el archivo .env en la carpeta del proyecto con parámetros acorde
a su sistema los valores de PYTHON y LOGISIM. Vea la seccion "Soporte para Windows" para
saber que escribir.

Ahora podra ejecutar los tests tanto individualmente como todos de una tirada.

IMPORTANTE: No se encontro una forma de detener la ejecucion de un test por timeout, asi que
si su micro nunca envia la salida Halt=1, un test puede quedarse corriendo eternamente.
Para ello, deberan crear un circuito contador similar al que se muestra en la imagen adjunta.
Esto NO es obligatorio, pero si el micro todavia no es funcional, podra quedarse corriendo
la prueba sin nunca terminar, asi que recomiendo que lo hagan, pero es su decision.

Ubicacion: S-MIPS Board (esto no afectara al funcionamiento de su micro al ser probado
sin estas modificaciones.)

Entradas:
HLT (Tunnel): El flag Halt emitido como salida del CPU.
TTY EN 1 (Tunnel): El flag TTY EN emitido como salida del CPU.
TTY DATA 1 (Tunnel): El flag TTY DATA emitido como salida del CPU.
CLK: Reloj
RST: Reset

Salidas:
halt (Pin): El pin de salida Halt que esstaba conectado originalmente al CPU.
TTY EN (Tunnel): El flag TTY EN enviado a la terminal.
TTY DATA (Tunnel): El flag TTY DATA enviado a la terminal.

Funcionamiento:

El circuito se divide en tres partes:
1- Un counter que cuenta la cantidad de ciclos que ha hecho el reloj. Cuando el valor del contador
llegue al valor maximo permitido para la cantidad de bits con los que cuenta (asegurarse de
configurar el contador en "Stay on value" cuando cause overflow), emitira una flag
para activar el flip-flop, continuando a la siguiente seccion. La constante que se especifique
es la cantidad de ciclos maximo que correra Logisim antes de dar "timeout".

2- Con el flip-flop activo, se emitira informacion a la terminal para anular su estado. Los tests
comprueban que el micro funciona correctamente comparando el texto emitido en la terminal con
el texto esperado. Invalidar este texto con caracteres permite darse cuenta de que un test
no termino su ejecucion correctamente y dio "timeout".

3- Cuando la salida haya sido invalidada tras un par de ciclos, se emite la salida halt verdadera,
terminando la ejecucion del test, incluso si el micro no ha enviado una flag de halt.

































