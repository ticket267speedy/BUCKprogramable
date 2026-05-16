#!/usr/bin/env python3
"""
mock_arduino.py — Simulador standalone del Arduino para Linux (pty).

Crea un par de pseudo-terminales (master/slave) usando el módulo pty de Python.
El extremo "esclavo" se comporta como un puerto serial real: lo pasas a la app.
El extremo "maestro" es controlado por este script, que responde a los comandos
del protocolo buck como lo haría el firmware del Arduino.

CUÁNDO USAR ESTE SCRIPT:
    - Cuando quieres probar con el puerto serial real (no el MockSerialClient interno).
    - Útil para detectar bugs de parseo o timing que no aparecen con el mock interno.

USO (Linux únicamente):
    Terminal 1: python3 mock_arduino.py
                → imprime algo como "Puerto virtual: /dev/pts/3"
    Terminal 2: python3 app.py
                → en la UI, conecta al puerto "/dev/pts/3"

NOTA PARA WINDOWS:
    El módulo `pty` no existe en Windows. Opciones equivalentes:
    A) Usa el checkbox "Modo simulación" en la UI (MockSerialClient integrado).
    B) Instala com0com (https://sourceforge.net/projects/com0com/) para crear
       un par de puertos COM virtuales (ej. COM10 ↔ COM11). Luego ejecuta este
       script adaptado para Windows con pyserial abriendo COM10, y conecta la
       app Flask al COM11.
"""

import os
import sys
import random
import threading
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mock_arduino")


def main():
    if sys.platform != "linux":
        print("Este script solo funciona en Linux (requiere el módulo 'pty').")
        print("En Windows, usa el checkbox 'Modo simulación' en la interfaz web.")
        sys.exit(0)

    try:
        import pty
    except ImportError:
        print("Error: módulo 'pty' no disponible.")
        sys.exit(1)

    # openpty() retorna dos file descriptors:
    # master_fd: este script lo lee/escribe (simula el HC-05)
    # slave_fd:  la app Flask lo ve como un puerto serial normal
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)   # ej. "/dev/pts/3"

    logger.info("═" * 50)
    logger.info(f"Puerto virtual creado: {slave_name}")
    logger.info(f"Conecta la app Flask al puerto: {slave_name}")
    logger.info("Baudios: cualquiera (pty ignora la velocidad)")
    logger.info("Presiona Ctrl+C para detener")
    logger.info("═" * 50)

    # Estado interno del convertidor buck simulado
    state = {
        "setpoint": 0.0,
        "v_out":    0.0,
        "fault":    False,
    }

    # Hilo de dinámica: actualiza v_out continuamente (lazo PI de primer orden)
    def _dynamics_loop():
        while True:
            state["v_out"] += 0.15 * (state["setpoint"] - state["v_out"])
            time.sleep(0.05)

    threading.Thread(target=_dynamics_loop, daemon=True).start()

    # Bucle de lectura de comandos desde el master_fd
    buf = b""
    while True:
        try:
            chunk = os.read(master_fd, 256)
        except OSError as exc:
            logger.error(f"Error leyendo del pty: {exc}")
            break

        buf += chunk

        # Procesamos líneas completas (terminadas en \n)
        while b"\n" in buf:
            raw_line, buf = buf.split(b"\n", 1)
            cmd = raw_line.decode("utf-8", errors="replace").strip()
            if not cmd:
                continue

            logger.info(f"RX ← {cmd!r}")
            response = _process_command(cmd, state)
            logger.info(f"TX → {response!r}")

            try:
                os.write(master_fd, (response + "\n").encode("utf-8"))
            except OSError as exc:
                logger.error(f"Error escribiendo al pty: {exc}")
                break


def _process_command(cmd: str, state: dict) -> str:
    """
    Implementa el mismo protocolo ASCII que el firmware del Arduino.
    Idéntico a MockSerialClient.send_command() pero sin la latencia simulada.
    """
    if cmd.startswith("SET V"):
        try:
            value = float(cmd.split()[2])
        except (IndexError, ValueError):
            return "ERR FORMATO_INVALIDO"
        if not (0.0 <= value <= 9.0):
            return "ERR RANGO_INVALIDO"
        state["setpoint"] = value
        return "OK"

    elif cmd == "GET V":
        noise = random.gauss(0, 0.02)
        return f"V {max(0.0, state['v_out'] + noise):.2f}"

    elif cmd == "GET I":
        i = max(0.0, state["v_out"] / 6.0 + random.gauss(0, 0.01))
        return f"I {i:.2f}"

    elif cmd == "GET STATUS":
        i = state["v_out"] / 6.0
        if state["fault"]:
            return "STATUS OVERCURRENT"
        if i > 2.1:
            state["fault"] = True
            return "STATUS OVERCURRENT"
        if state["v_out"] > 9.1:
            return "STATUS OVERVOLTAGE"
        return "STATUS OK"

    elif cmd == "RESET":
        state["fault"] = False
        return "OK"

    return "ERR UNKNOWN_CMD"


if __name__ == "__main__":
    main()
