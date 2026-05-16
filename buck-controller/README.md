# Buck Converter Controller

Interfaz web local para monitorear y controlar remotamente un convertidor DC-DC
tipo buck programable, usando un módulo Bluetooth HC-05 y un Arduino UNO.

## Estructura del proyecto

```
buck-controller/
├── app.py                          # Servidor Flask + WebSocket (Controller)
├── serial_client.py                # Comunicación HC-05 + MockSerialClient
├── services/
│   └── buck_service.py             # Lógica de negocio (Service)
├── repositories/
│   └── telemetry_repository.py     # Historial en RAM (Repository)
├── models/
│   └── telemetry.py                # Estructuras de datos (Model)
├── templates/
│   └── index.html                  # Interfaz web (View)
├── static/
│   ├── main.js                     # Socket.IO + Chart.js (frontend)
│   └── style.css                   # Tema oscuro
├── mock_arduino.py                 # Simulador standalone (solo Linux)
├── requirements.txt
└── README.md
```

## Instalación

Requiere Python 3.10 o superior.

```bash
cd buck-controller
pip install -r requirements.txt
```

## Emparejamiento del HC-05

### Windows 10/11

1. Enciende el HC-05 (LED parpadeando rápido = modo AT, lento = emparejable).
2. Ve a **Configuración → Bluetooth y dispositivos → Agregar dispositivo**.
3. Selecciona el HC-05. PIN: `1234` (o `0000`).
4. Abre **Panel de control → Dispositivos e impresoras**.
5. Clic derecho en el HC-05 → **Propiedades → Servicios** o **Hardware**.
6. Anota el número del puerto COM (ej. `COM5`). Es el que usarás en la app.

> Alternativa: abre **Administrador de dispositivos → Puertos (COM y LPT)**
> y busca el puerto recién creado por el HC-05.

### Linux (Ubuntu/Debian)

```bash
# 1. Empareja el HC-05 con bluetoothctl
bluetoothctl
> scan on
# Espera a ver la MAC del HC-05, ej: AA:BB:CC:DD:EE:FF
> pair   AA:BB:CC:DD:EE:FF
> trust  AA:BB:CC:DD:EE:FF
> quit

# 2. Crea el puerto virtual rfcomm
sudo rfcomm bind 0 AA:BB:CC:DD:EE:FF
# El puerto queda disponible como /dev/rfcomm0

# Para liberar al terminar la sesión:
sudo rfcomm release 0
```

## Arrancar el servidor

### Modo normal (con HC-05 y Arduino)

```bash
python app.py
```

Abre http://localhost:5000 en el navegador.

En el **Panel de Conexión**:
- Ingresa el puerto (`COM5` en Windows, `/dev/rfcomm0` en Linux).
- Selecciona los baudios (default: `9600`, debe coincidir con la config del HC-05).
- Clic en **Conectar**.

### Modo simulación (sin hardware)

```bash
python app.py --mock
```

O desde la interfaz: activa el checkbox **"Modo simulación"** antes de conectar.

La simulación modela un convertidor buck real con:
- Dinámica de primer orden (τ ≈ 1.5 s).
- Carga de 6 Ω (I_out ≈ V_out / 6).
- Ruido gaussiano en el ADC (σ_V = 20 mV, σ_I = 10 mA).
- Falta OVERCURRENT si I_out > 2.1 A (limpiable con "Reset faltas").

### Servidor en un puerto diferente

```bash
python app.py --port 8080
```

### Acceso desde otro dispositivo en la red local

La app escucha en `0.0.0.0`, así que cualquier dispositivo en tu red local
puede acceder en `http://<IP_de_tu_PC>:5000`.

## Protocolo de comunicación Arduino

| Dirección    | Comando        | Respuesta           | Descripción                    |
|--------------|----------------|---------------------|-------------------------------|
| PC→Arduino   | `SET V 5.50\n` | `OK\n`              | Fija setpoint en 5.50 V       |
| PC→Arduino   | `GET V\n`      | `V 5.48\n`          | Lee V_out actual               |
| PC→Arduino   | `GET I\n`      | `I 0.91\n`          | Lee I_out actual               |
| PC→Arduino   | `GET STATUS\n` | `STATUS OK\n`       | Lee código de estado           |
| PC→Arduino   | `RESET\n`      | `OK\n`              | Limpia faltas activas          |
| Arduino→PC   | `ERR msg\n`    | —                   | Error del Arduino              |

Códigos de estado: `OK` · `OVERCURRENT` · `OVERVOLTAGE` · `DCM`

## Eventos WebSocket

### Servidor → Navegador

| Evento             | Payload                                                |
|--------------------|--------------------------------------------------------|
| `telemetry`        | `{v_out, i_out, status, timestamp, setpoint}`         |
| `connection_status`| `{connected, port, error}`                            |
| `command_log`      | `{entries: [...]}`                                     |
| `history_data`     | `{timestamps: [...], v_out: [...], i_out: [...]}`     |
| `setpoint_result`  | `{success, error?}`                                    |
| `reset_result`     | `{success, error?}`                                    |

### Navegador → Servidor

| Evento              | Payload                        |
|---------------------|--------------------------------|
| `connect_device`    | `{port, baudrate, mock}`       |
| `disconnect_device` | `{}`                           |
| `set_voltage`       | `{value}`                      |
| `reset_faults`      | `{}`                           |
| `request_history`   | `{}`                           |

## Simulador standalone (solo Linux)

```bash
# Terminal 1:
python3 mock_arduino.py
# Imprime algo como: "Puerto virtual: /dev/pts/3"

# Terminal 2:
python3 app.py
# En la UI conecta al puerto /dev/pts/3
```

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `Cannot open port 'COM5'` | Puerto ocupado o HC-05 no emparejado | Verifica que ningún otro programa use el puerto; reempareja el HC-05 |
| Sin datos en las gráficas | Arduino sin firmware cargado | Carga el sketch del Arduino; usa modo simulación para verificar la UI |
| WebSocket no conecta | `eventlet` no instalado | `pip install eventlet` |
| Gráfica vacía tras reconectar | El historial del servidor persiste | Recarga la página para solicitar el historial actual |
| Timeout 300 ms en todos los comandos | Baudios incorrectos | Verifica que la app y el HC-05 usen los mismos baudios |

## Dependencias

| Paquete | Versión | Propósito |
|---------|---------|-----------|
| Flask | 3.0.3 | Framework web + rutas HTTP |
| flask-socketio | 5.3.6 | WebSockets bidireccionales |
| pyserial | 3.5 | Puerto serial del HC-05 |
| eventlet | 0.35.2 | Backend async para WebSockets reales |
