"""
models/telemetry.py — Estructuras de datos del sistema.

Define las entidades que viajan entre Repository, Service y Controller.
Se usan dataclasses (Python 3.7+) en lugar de dicts para tener
tipado estático y acceso por atributo (no por clave de string).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TelemetryReading:
    """
    Representa una muestra de telemetría tomada en un instante de tiempo.

    Los campos de medición son Optional porque el Arduino puede no responder
    dentro del timeout (300 ms), en cuyo caso el Service guarda None
    en lugar de un valor incorrecto.
    """
    timestamp: float           # Unix timestamp (time.time()) — segundos desde epoch
    v_out:     Optional[float] # Voltaje de salida medido (V), None si timeout
    i_out:     Optional[float] # Corriente de salida medida (A), None si timeout
    status:    str             # Código de estado: "OK" / "OVERCURRENT" / "OVERVOLTAGE" / "DCM"


@dataclass
class SystemState:
    """
    Estado mutable del sistema en un momento dado.

    El Repository mantiene una única instancia de este objeto y la actualiza
    con cada ciclo de polling. El Controller la lee para responder al
    evento 'connect' de un nuevo cliente WebSocket.
    """
    connected:     bool            = False    # ¿Puerto serial abierto y activo?
    port:          str             = ""       # "COM5", "/dev/rfcomm0", etc.
    baudrate:      int             = 9600
    setpoint:      float           = 0.0     # Último setpoint enviado al Arduino (V)
    last_v_out:    Optional[float] = None    # Última lectura de voltaje
    last_i_out:    Optional[float] = None    # Última lectura de corriente
    last_status:   str             = "UNKNOWN"
    error_message: str             = ""      # Vacío cuando no hay error activo
