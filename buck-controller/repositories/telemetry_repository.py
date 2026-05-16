"""
repositories/telemetry_repository.py — Almacenamiento en memoria (RAM).

No usamos base de datos porque la telemetría es efímera: solo necesitamos
los últimos 60 segundos para la gráfica. Un deque con maxlen es O(1)
para insertar y descartar, y no requiere limpiar manualmente.

Por qué RLock y no Lock:
    RLock (Reentrant Lock) permite que el MISMO hilo adquiera el lock
    más de una vez sin bloquearse a sí mismo. Útil si un método público
    (ej. update_state) llama internamente a otro método que también
    pide el lock — con Lock normal eso causaría deadlock.
"""

import time
import threading
from collections import deque
from typing import List

from models.telemetry import TelemetryReading, SystemState

HISTORY_SECONDS = 60    # ventana de tiempo visible en la gráfica
SAMPLE_RATE_HZ  = 2     # el Service hace polling cada 500 ms → 2 Hz
MAX_SAMPLES     = HISTORY_SECONDS * SAMPLE_RATE_HZ   # = 120 muestras


class TelemetryRepository:
    """
    Capa de acceso a datos (en RAM) para telemetría e historial de comandos.

    Todos los métodos son thread-safe: el hilo de polling y el hilo de
    Flask-SocketIO pueden llamar simultáneamente sin condiciones de carrera.
    """

    def __init__(self):
        self._lock = threading.RLock()

        # deque con maxlen actúa como buffer circular:
        # cuando llega la muestra 121, la más antigua se elimina automáticamente.
        self._history: deque = deque(maxlen=MAX_SAMPLES)

        # Estado mutable del sistema (una sola instancia compartida)
        self._state = SystemState()

        # Log de las últimas 20 líneas de comandos TX/RX
        self._command_log: deque = deque(maxlen=20)

    # ── Historial de telemetría ───────────────────────────────────────────────

    def add_reading(self, reading: TelemetryReading) -> None:
        """Agrega una muestra al buffer circular. El más antiguo se descarta solo."""
        with self._lock:
            self._history.append(reading)

    def get_history(self) -> List[TelemetryReading]:
        """
        Retorna una copia de lista del historial.
        Convertimos a lista para que sea seguro serializar fuera del lock.
        """
        with self._lock:
            return list(self._history)

    def clear_history(self) -> None:
        """Vacía el historial (útil en tests o al reconectar)."""
        with self._lock:
            self._history.clear()

    # ── Estado del sistema ────────────────────────────────────────────────────

    def update_state(self, **kwargs) -> None:
        """
        Actualiza campos del SystemState por nombre.

        Uso: repo.update_state(connected=True, last_v_out=5.2)

        Lanzamos AttributeError si la clave no existe en SystemState,
        para detectar typos en tiempo de desarrollo, no en producción silenciosa.
        """
        with self._lock:
            for key, value in kwargs.items():
                if not hasattr(self._state, key):
                    raise AttributeError(
                        f"SystemState no tiene el campo '{key}'. "
                        f"Campos válidos: {list(self._state.__dataclass_fields__)}"
                    )
                setattr(self._state, key, value)

    def get_state(self) -> SystemState:
        """Retorna el SystemState actual. Es referencia, no copia — solo lectura."""
        with self._lock:
            return self._state

    # ── Log de comandos ───────────────────────────────────────────────────────

    def add_log_entry(self, message: str) -> None:
        """
        Agrega una línea al log de comandos con timestamp HH:MM:SS.
        El deque con maxlen=20 descarta la más antigua automáticamente.
        """
        with self._lock:
            ts = time.strftime('%H:%M:%S')
            self._command_log.append(f"[{ts}] {message}")

    def get_log(self) -> List[str]:
        """Retorna las últimas 20 líneas del log como lista."""
        with self._lock:
            return list(self._command_log)
