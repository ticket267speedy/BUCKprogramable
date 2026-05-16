Hola Claude. Necesito que me ayudes a desarrollar una aplicación web 
con Python Flask para controlar y monitorear remotamente un convertidor 
buck programable. Contexto completo del proyecto:

CONTEXTO DEL PROYECTO HARDWARE:
- Soy estudiante de Electrónica de Potencia en Perú.
- Estoy construyendo un convertidor DC-DC tipo buck programable: 
  entrada 12V DC, salida 0-9V variable, corriente nominal 2A.
- Hardware: MOSFET P-channel IRF4905, diodo Schottky 1N5822, 
  inductor 220µH, capacitor 47µF low ESR, frecuencia switching 31.25 kHz.
- Control embebido: Arduino UNO (se migrará luego a ATmega328P standalone).
- Sensor de corriente: ACS712-5A.
- Display local: OLED 0.96" I2C.
- Comunicación inalámbrica: módulo HC-05 (Bluetooth SPP, baudios 9600).
- El Arduino implementa un lazo PI digital para regular Vout al setpoint.

LO QUE NECESITO QUE DESARROLLES:
Una aplicación local con Python + Flask que:

1. Se conecta vía Bluetooth al módulo HC-05 emparejado con la PC.
   Usa `pyserial` para abrir el puerto serial virtual (Windows: COMx, 
   Linux: /dev/rfcomm0). El puerto y los baudios deben ser configurables.

2. Expone una interfaz web local accesible desde el navegador (puerto 5000 
   por defecto), responsive, con tres áreas:
   
   (a) PANEL DE CONTROL:
       - Slider para seleccionar setpoint de voltaje (0 a 9 V, paso 0.1 V).
       - Campo numérico alternativo para ingresar el setpoint manualmente.
       - Botón "Aplicar setpoint".
       - Botón "Reset faltas" (limpia errores).
   
   (b) PANEL DE TELEMETRÍA:
       - Visualización en tiempo real (cada 500 ms) de:
         * Voltaje de salida medido (V_out).
         * Corriente de salida medida (I_out).
         * Estado del sistema (OK / OVERCURRENT / OVERVOLTAGE / DCM).
       - Gráfico de líneas histórico (últimos 60 segundos) para V_out e I_out.
   
   (c) PANEL DE CONEXIÓN:
       - Estado de la conexión Bluetooth (conectado/desconectado, RSSI si es posible).
       - Botón conectar/desconectar.
       - Log de comandos enviados/recibidos (últimas 20 líneas).

3. Comunica con el Arduino usando este protocolo ASCII simple terminado en \n:
   - Comandos PC → Arduino:
     * `SET V <valor>\n` → fija setpoint en voltios. Ej: `SET V 5.5`
     * `GET V\n` → pide V_out actual.
     * `GET I\n` → pide I_out actual.
     * `GET STATUS\n` → pide código de estado.
     * `RESET\n` → limpia faltas.
   - Respuestas Arduino → PC:
     * `OK\n` o `ERR <mensaje>\n` (confirmación de comandos)
     * `V <valor>\n` (respuesta a GET V)
     * `I <valor>\n` (respuesta a GET I)
     * `STATUS <code>\n` (respuesta a GET STATUS)

REQUISITOS TÉCNICOS DEL CÓDIGO:
- Python 3.10+.
- Dependencias mínimas: Flask, flask-socketio, pyserial.
- Estructura modular: separar `app.py` (Flask + WebSocket), 
  `serial_client.py` (manejo del HC-05), `templates/index.html`, 
  `static/main.js` y `static/style.css`.
- Comunicación PC-navegador con WebSocket para refresco en tiempo real 
  (sin polling HTTP).
- Manejo robusto de errores: reconexión automática si el HC-05 se desconecta, 
  timeouts en los comandos seriales (300 ms), validación de rango del setpoint.
- Logs claros con `logging` de Python.
- Comentarios en español explicando QUÉ hace cada función y POR QUÉ está allí.

ESTILO Y EXPLICACIONES:
- Antes de escribir código, explica brevemente la arquitectura general y 
  las decisiones clave de diseño.
- Después de cada archivo importante, explica las funciones más críticas 
  línea por línea (no asumas que conozco las librerías que importas).
- Usa fuentes confiables (documentación oficial de Flask, pyserial, 
  Socket.IO) y cítalas cuando expliques algo no obvio.
- Detalla el README con instrucciones paso a paso para Windows y Linux 
  para emparejar el HC-05 y arrancar el servidor.

ENTREGABLE:
1. Estructura completa de archivos.
2. Código de cada archivo, comentado y explicado.
3. README con setup paso a paso.
4. Indicación clara de cómo probar el sistema sin Arduino físico 
   (mock del HC-05 que responda a los comandos para probar la UI).

Empezamos con la arquitectura general y vamos por bloques. 
Pregúntame lo que necesites antes de programar.