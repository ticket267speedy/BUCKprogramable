# Convertidor BUCK DC-DC Reductor Programable

Proyecto de control de un convertidor BUCK mediante comunicación Bluetooth (HC-05), desarrollado para el curso de Electrónica de Potencia.

## Estructura del repositorio

```
├── buck-controller/     App web Flask + SocketIO para control remoto vía HC-05
├── firmware/            Proyectos Atmel Studio (AVR/GCC) del microcontrolador
├── src/                 Archivos fuente C y cabeceras sueltas (pruebas y módulos)
└── docs/                Documentación: cálculos, informes y guías del proyecto
```

## Módulos

### `buck-controller/` — Interfaz web
Aplicación Python que recibe comandos desde el navegador y los reenvía al Arduino vía puerto serial Bluetooth.

- **Stack:** Flask, Flask-SocketIO, pyserial
- **Inicio:** `pip install -r requirements.txt` → `python app.py`
- Para pruebas sin hardware: `python mock_arduino.py`

### `firmware/` — Firmware AVR
Proyectos de Atmel Studio 7 con el código embebido del microcontrolador.

| Proyecto | Descripción |
|---|---|
| `GccApplication1` | Prueba base inicial |
| `EnvioComandosCelularEmbebido` | Comunicación UART con HC-05 y pantalla OLED |
| `IntegracionParcial` | Integración PWM + OLED + UART |
| `TestFuncionamientoUSBASP` | Verificación del programador USBASP |

### `src/` — Fuentes C
Archivos `.c` / `.h` de módulos y pruebas independientes (PWM, OLED, UART, blink).

### `docs/` — Documentación
Cálculos de diseño, informe del proyecto y guía de compras de componentes.
