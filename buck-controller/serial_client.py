"""
serial_client.py — Comunicación serial con el módulo HC-05.

Patrón de comunicación: request-response sincrónico.
    1. send_command() adquiere el lock del puerto.
    2. Envía el comando terminado en \\n.
    3. Llama a readline() que bloquea hasta recibir \\n o expirar el timeout.
    4. Retorna la línea recibida (o None si hubo timeout/error).

Por qué un Lock y no colas asíncronas:
    El protocolo del Arduino es estrictamente request-response de una sola
    línea. No hay push espontáneo del Arduino (salvo que el firmware lo
    implemente). Con un Lock basta: solo UN hilo envía+espera a la vez.
    Colas asíncronas añadirían complejidad sin beneficio aquí.

Por qué reset_input_buffer antes de cada envío:
    Si el Arduino llegó a responder algo antes del timeout anterior
    y esa respuesta quedó en el buffer del SO, leerla ahora nos daría
    una respuesta "vieja" para el comando "nuevo". Vaciamos el buffer
    para garantizar que la siguiente readline() devuelva la respuesta
    al comando recién enviado.
"""

import random
import threading
import time
import logging
from typing import Callable, Optional, Tuple

import serial   # pyserial — documentación: https://pyserial.readthedocs.io/

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT_S  = 0.3   # 300 ms máximo para que el Arduino responda
RECONNECT_INTERVAL = 5.0   # segundos entre intentos de reconexión automática


class SerialClient:
    """
    Abre y gestiona el puerto serial virtual del HC-05 (emparejado vía Bluetooth).

    El par de hilos internos:
        - _reconnect_loop: un hilo daemon que duerme RECONNECT_INTERVAL segundos
          y reintenta conectar si self._connected es False.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        on_disconnect: Optional[Callable] = None,
    ):
        """
        port:          Puerto serial, ej. "COM5" (Windows) o "/dev/rfcomm0" (Linux).
        baudrate:      Velocidad en baudios; debe coincidir con la config del HC-05.
        on_disconnect: Callback opcional que se llama cuando se detecta una
                       desconexión inesperada, para notificar al Controller.
        """
        self._port         = port
        self._baudrate     = baudrate
        self._on_disconnect = on_disconnect

        self._serial: Optional[serial.Serial] = None
        # El Lock garantiza que solo un hilo esté dentro de send_command() a la vez.
        # threading.Lock es monkey-patchado por eventlet, así que funciona
        # correctamente con los green threads de Flask-SocketIO.
        self._lock         = threading.Lock()
        self._connected    = False
        self._running      = False   # False detiene el hilo de reconexión

    # ── API pública ───────────────────────────────────────────────────────────

    def connect(self) -> Tuple[bool, str]:
        """
        Abre el puerto serial.

        Retorna: (True, "") en éxito, o (False, mensaje_error) en fallo.

        serial.Serial() lanza SerialException si el puerto no existe,
        está ocupado por otra app, o el HC-05 no está emparejado.
        El timeout=COMMAND_TIMEOUT_S hace que readline() no bloquee
        indefinidamente: si el Arduino no responde en 300 ms, readline()
        devuelve b"" y nosotros interpretamos eso como timeout.
        """
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=COMMAND_TIMEOUT_S,
            )
            self._connected = True
            self._running   = True
            logger.info(f"Puerto {self._port} abierto a {self._baudrate} bps")
            self._start_reconnect_watcher()
            return True, ""
        except serial.SerialException as exc:
            msg = f"No se pudo abrir '{self._port}': {exc}"
            logger.error(msg)
            return False, msg

    def disconnect(self) -> None:
        """Cierra el puerto y detiene el hilo de reconexión."""
        self._running   = False
        self._connected = False
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info(f"Puerto {self._port} cerrado")

    def send_command(self, cmd: str) -> Optional[str]:
        """
        Envía `cmd` al Arduino y retorna la respuesta como string limpio,
        o None si hubo timeout o error de comunicación.

        Flujo interno:
            1. Verifica conexión (salida rápida si está desconectado).
            2. Adquiere el Lock (bloquea si otro hilo está usando el puerto).
            3. Vacía el buffer de entrada (evita leer respuestas viejas).
            4. Escribe "cmd\\n" codificado en UTF-8.
            5. Llama readline() — bloquea hasta \\n o hasta COMMAND_TIMEOUT_S.
            6. Decodifica y retorna la línea, o None si readline() devolvió b"".
        """
        if not self._connected:
            logger.debug(f"send_command omitido (sin conexión): {cmd!r}")
            return None

        with self._lock:
            try:
                self._serial.reset_input_buffer()
                self._serial.write(f"{cmd}\n".encode("utf-8"))
                self._serial.flush()
                logger.debug(f"TX → {cmd!r}")

                raw = self._serial.readline()   # bytes o b"" si timeout
                if not raw:
                    logger.warning(f"Timeout esperando respuesta a: {cmd!r}")
                    return None

                response = raw.decode("utf-8", errors="replace").strip()
                logger.debug(f"RX ← {response!r}")
                return response

            except serial.SerialException as exc:
                logger.error(f"Error en puerto serial: {exc}")
                self._connected = False
                # Notificamos al Controller en un hilo separado para no
                # bloquear dentro del Lock (el callback podría llamar a socketio.emit)
                if self._on_disconnect:
                    threading.Thread(
                        target=self._on_disconnect, daemon=True
                    ).start()
                return None

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Reconexión automática ─────────────────────────────────────────────────

    def _start_reconnect_watcher(self) -> None:
        """Lanza el hilo daemon de reconexión."""
        t = threading.Thread(
            target=self._reconnect_loop,
            name="serial-reconnect",
            daemon=True,   # muere cuando muere el proceso principal
        )
        t.start()

    def _reconnect_loop(self) -> None:
        """
        Cada RECONNECT_INTERVAL segundos verifica si la conexión se perdió.
        Si es así, intenta reabrir el puerto. Si tiene éxito, el flag
        self._connected vuelve a True y el polling retoma automáticamente.
        """
        while self._running:
            time.sleep(RECONNECT_INTERVAL)
            if self._running and not self._connected:
                logger.info(f"Intentando reconectar en '{self._port}'…")
                try:
                    if self._serial:
                        self._serial.close()
                    self._serial = serial.Serial(
                        port=self._port,
                        baudrate=self._baudrate,
                        timeout=COMMAND_TIMEOUT_S,
                    )
                    self._connected = True
                    logger.info("Reconexión exitosa")
                except serial.SerialException as exc:
                    logger.warning(f"Reconexión fallida: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
#  MockSerialClient — Simulador del HC-05 para pruebas sin hardware
# ══════════════════════════════════════════════════════════════════════════════

class MockSerialClient:
    """
    Simula el comportamiento del Arduino + convertidor buck sin hardware real.

    Modelo físico implementado:
        - Dinámica de primer orden: V_out(k+1) = V_out(k) + α·(Vsp - V_out(k))
          donde α = 0.15 (τ ≈ 3 ciclos de polling ≈ 1.5 s de tiempo de establecimiento).
        - Carga resistiva de 6 Ω (I_out = V_out / 6, corriente nominal ≈ 1.5 A a 9 V).
        - Ruido gaussiano en V_out (σ = 20 mV) e I_out (σ = 10 mA) para simular ADC real.
        - Falta OVERCURRENT si I_out supera 2.1 A (limpiar con RESET).
        - Latencia de 50 ms para simular el RTT del Bluetooth SPP.
    """

    def __init__(self):
        self._setpoint = 0.0
        self._v_out    = 0.0
        self._alpha    = 0.15   # constante de tiempo de la respuesta dinámica
        self._fault    = False  # simula una falta activa de OVERCURRENT
        self._lock     = threading.Lock()
        self._connected = True

    def connect(self) -> Tuple[bool, str]:
        self._connected = True
        logger.info("MockSerialClient: modo simulación activo")
        return True, ""

    def disconnect(self) -> None:
        self._connected = False
        logger.info("MockSerialClient: desconectado")

    def send_command(self, cmd: str) -> Optional[str]:
        """
        Procesa el comando y retorna la respuesta que daría el Arduino.
        Llama a _update_dynamics() en cada invocación para que la simulación
        avance en el tiempo (el polling llama a esto cada 500 ms).
        """
        time.sleep(0.05)   # latencia Bluetooth simulada (50 ms RTT)

        cmd = cmd.strip()
        with self._lock:
            self._update_dynamics()   # avanza la simulación física

            if cmd.startswith("SET V"):
                return self._handle_set_v(cmd)
            elif cmd == "GET V":
                noise = random.gauss(0, 0.02)
                return f"V {max(0.0, self._v_out + noise):.2f}"
            elif cmd == "GET I":
                i = max(0.0, self._v_out / 6.0 + random.gauss(0, 0.01))
                return f"I {i:.2f}"
            elif cmd == "GET STATUS":
                return self._handle_get_status()
            elif cmd == "RESET":
                self._fault = False
                return "OK"
            else:
                return "ERR UNKNOWN_CMD"

    def _update_dynamics(self) -> None:
        """Ecuación de diferencias de primer orden — avanza un paso de simulación."""
        self._v_out += self._alpha * (self._setpoint - self._v_out)

    def _handle_set_v(self, cmd: str) -> str:
        try:
            value = float(cmd.split()[2])
        except (IndexError, ValueError):
            return "ERR FORMATO_INVALIDO"
        if not (0.0 <= value <= 9.0):
            return "ERR RANGO_INVALIDO"
        self._setpoint = value
        return "OK"

    def _handle_get_status(self) -> str:
        i_out = self._v_out / 6.0
        if self._fault:
            return "STATUS OVERCURRENT"
        if i_out > 2.1:
            self._fault = True
            return "STATUS OVERCURRENT"
        if self._v_out > 9.1:
            return "STATUS OVERVOLTAGE"
        return "STATUS OK"

    @property
    def connected(self) -> bool:
        return self._connected
