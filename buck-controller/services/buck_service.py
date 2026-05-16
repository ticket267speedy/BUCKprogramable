"""
services/buck_service.py — Lógica de negocio del controlador buck.

Esta capa es el "cerebro" de la aplicación:
    - Valida que el setpoint esté en el rango físico del convertidor [0-9 V].
    - Orquesta el ciclo de polling (GET V / GET I / GET STATUS cada 500 ms).
    - Emite la telemetría a todos los navegadores conectados vía SocketIO.
    - Guarda las muestras en el repositorio para el historial de la gráfica.

NO conoce Flask, NO conoce HTML, NO conoce el puerto serial directamente:
solo habla con sus dependencias inyectadas (serial_client, repository, socketio).
Esto hace que sea fácil de probar en aislamiento.
"""

import time
import logging
from typing import Optional

from models.telemetry import TelemetryReading
from repositories.telemetry_repository import TelemetryRepository

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.5   # 500 ms entre ciclos de telemetría
V_MIN = 0.0             # voltaje mínimo del convertidor (V)
V_MAX = 9.0             # voltaje máximo del convertidor (V)


class BuckService:
    """
    Orquesta la comunicación con el Arduino y el flujo de telemetría.

    Dependencias inyectadas en __init__ (patrón Dependency Injection):
        serial_client : SerialClient o MockSerialClient — abstrae el hardware.
        repository    : TelemetryRepository — guarda historial y estado.
        socketio      : instancia de Flask-SocketIO — emite eventos al navegador.

    Por qué socketio.start_background_task en lugar de threading.Thread:
        Flask-SocketIO con eventlet usa green threads (coroutines cooperativas).
        start_background_task() registra la tarea en el event loop de eventlet,
        permitiendo que socketio.emit() funcione correctamente desde el hilo
        de polling. Si usáramos threading.Thread directamente, la emisión
        podría fallar o bloquear en ciertos contextos de eventlet.
        Ref: https://flask-socketio.readthedocs.io/en/latest/getting_started.html
    """

    def __init__(self, serial_client, repository: TelemetryRepository, socketio):
        self._serial     = serial_client
        self._repo       = repository
        self._sio        = socketio
        self._polling    = False   # flag que detiene el bucle de polling

    # ── API pública ───────────────────────────────────────────────────────────

    def start_polling(self) -> None:
        """
        Lanza el bucle de polling como tarea de background de SocketIO.
        Si ya está corriendo, no hace nada (idempotente).
        """
        if self._polling:
            logger.debug("Polling ya está activo, se ignora la segunda llamada")
            return
        self._polling = True
        # start_background_task registra _poll_loop en el event loop de eventlet
        self._sio.start_background_task(self._poll_loop)
        logger.info("Polling de telemetría iniciado (intervalo: 500 ms)")

    def stop(self) -> None:
        """
        Detiene el polling y cierra la conexión serial.
        El bucle _poll_loop verifica self._polling en cada iteración y saldrá.
        """
        self._polling = False
        self._serial.disconnect()
        logger.info("BuckService detenido")

    def set_voltage(self, value) -> dict:
        """
        Valida y aplica un nuevo setpoint de voltaje al Arduino.

        Flujo:
            1. Valida que `value` sea convertible a float.
            2. Valida que esté en el rango físico [V_MIN, V_MAX].
            3. Envía "SET V x.x" y espera "OK" o "ERR ...".
            4. Si OK, actualiza el setpoint en el repositorio.

        Retorna: {'success': True} o {'success': False, 'error': '<mensaje>'}.
        """
        try:
            value = float(value)
        except (TypeError, ValueError):
            return {"success": False, "error": "El setpoint debe ser un número"}

        if not (V_MIN <= value <= V_MAX):
            return {
                "success": False,
                "error": f"Setpoint fuera de rango [{V_MIN:.1f} – {V_MAX:.1f} V]",
            }

        response = self._serial.send_command(f"SET V {value:.1f}")

        if response is None:
            return {"success": False, "error": "Sin respuesta del Arduino (timeout 300 ms)"}
        if response == "OK":
            self._repo.update_state(setpoint=value)
            return {"success": True}
        # El Arduino respondió ERR o algo inesperado
        return {"success": False, "error": response}

    def reset_faults(self) -> dict:
        """
        Envía el comando RESET al Arduino para limpiar faltas activas
        (OVERCURRENT, OVERVOLTAGE, etc.) y rearma el lazo PI.

        Retorna: {'success': True} o {'success': False, 'error': '<mensaje>'}.
        """
        response = self._serial.send_command("RESET")

        if response is None:
            return {"success": False, "error": "Sin respuesta del Arduino (timeout 300 ms)"}
        if response == "OK":
            self._repo.update_state(last_status="OK")
            return {"success": True}
        return {"success": False, "error": response}

    # ── Bucle de polling ──────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """
        Bucle principal de telemetría (corre como tarea de background de SocketIO).

        Cada iteración:
            1. Si no hay conexión, duerme 1 s y reintenta (espera reconexión).
            2. Consulta GET V, GET I, GET STATUS (3 comandos secuenciales).
            3. Guarda la muestra en el repositorio.
            4. Emite el evento 'telemetry' a TODOS los navegadores conectados.
            5. Duerme el tiempo restante del intervalo de 500 ms, compensando
               el tiempo que tardaron las tres consultas seriales.

        Por qué compensamos el tiempo:
            Cada send_command puede tardar hasta 300 ms (timeout).
            Sin compensación, el intervalo efectivo sería 500ms + tiempo_consultas,
            lo que desincronizaría el historial y la gráfica.
        """
        while self._polling:
            # ── Guardia de conexión: espera si el HC-05 se desconectó ────────
            if not self._serial.connected:
                logger.debug("Sin conexión serial — esperando reconexión…")
                time.sleep(1.0)
                continue

            t_inicio = time.monotonic()   # monotonic es más preciso que time.time() para medir intervalos

            v_out  = self._query_voltage()
            i_out  = self._query_current()
            status = self._query_status()

            # ── Persistencia en el repositorio ───────────────────────────────
            reading = TelemetryReading(
                timestamp=time.time(),
                v_out=v_out,
                i_out=i_out,
                status=status or "UNKNOWN",
            )
            self._repo.add_reading(reading)
            self._repo.update_state(
                last_v_out=v_out,
                last_i_out=i_out,
                last_status=status or "UNKNOWN",
            )

            # ── Emisión WebSocket a todos los clientes conectados ─────────────
            # socketio.emit() (sin contexto de request) emite a TODOS los clientes.
            # Ref: https://flask-socketio.readthedocs.io/en/latest/api.html
            self._sio.emit("telemetry", {
                "v_out":     v_out,
                "i_out":     i_out,
                "status":    status or "UNKNOWN",
                "timestamp": reading.timestamp,
                "setpoint":  self._repo.get_state().setpoint,
            })

            # ── Compensación de tiempo ────────────────────────────────────────
            elapsed    = time.monotonic() - t_inicio
            sleep_time = max(0.0, POLL_INTERVAL_S - elapsed)
            time.sleep(sleep_time)

        logger.info("Bucle de polling terminado")

    # ── Helpers de parsing ────────────────────────────────────────────────────

    def _query_voltage(self) -> Optional[float]:
        """Envía GET V y parsea la respuesta 'V <valor>' a float."""
        resp = self._serial.send_command("GET V")
        if resp and resp.startswith("V "):
            try:
                return float(resp[2:])
            except ValueError:
                logger.warning(f"GET V: respuesta no parseable: {resp!r}")
        return None

    def _query_current(self) -> Optional[float]:
        """Envía GET I y parsea la respuesta 'I <valor>' a float."""
        resp = self._serial.send_command("GET I")
        if resp and resp.startswith("I "):
            try:
                return float(resp[2:])
            except ValueError:
                logger.warning(f"GET I: respuesta no parseable: {resp!r}")
        return None

    def _query_status(self) -> Optional[str]:
        """Envía GET STATUS y extrae el código: 'OK', 'OVERCURRENT', etc."""
        resp = self._serial.send_command("GET STATUS")
        if resp and resp.startswith("STATUS "):
            return resp[7:]   # extrae todo lo que viene después de "STATUS "
        return None
