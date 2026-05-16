import argparse
import logging

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from models.telemetry import SystemState
from repositories.telemetry_repository import TelemetryRepository
from services.buck_service import BuckService
from serial_client import SerialClient, MockSerialClient

# ── Configuración del logger ──────────────────────────────────────────────────
# %(asctime)s  → fecha y hora de cada mensaje
# %(levelname)s → INFO, WARNING, ERROR, etc.
# %(name)s      → nombre del módulo que emite el log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Instancias de Flask y SocketIO ────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "buck-controller-dev-key"

# async_mode='threading': usa hilos estándar de Python para manejar conexiones.
# Es el modo más compatible con Windows. Flask-SocketIO usará simple-websocket
# (instalado en requirements.txt) para WebSockets reales sobre este modo.
# cors_allowed_origins='*': permite conexiones desde cualquier origen local.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# ── Singletons de la capa de datos y servicio ─────────────────────────────────
# TelemetryRepository: existe durante toda la vida del servidor (singleton).
# BuckService: se recrea cada vez que el usuario conecta un dispositivo,
# porque necesita una referencia al nuevo SerialClient.
telemetry_repo = TelemetryRepository()
buck_service: BuckService = None   # None = no hay conexión activa


# ══════════════════════════════════════════════════════════════════════════════
#  RUTAS HTTP (View → Controller)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Sirve la SPA (Single Page Application) desde templates/index.html."""
    return render_template("index.html")


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTOS WEBSOCKET — Servidor → Cliente y Cliente → Servidor
# ══════════════════════════════════════════════════════════════════════════════

@socketio.on("connect")
def handle_client_connect():
    """
    Se dispara automáticamente cuando un navegador abre el WebSocket.

    emit() aquí envía SOLO al cliente que acaba de conectar (no a todos).
    Sincronizamos el estado inmediatamente para que la UI no muestre valores
    inconsistentes si el usuario recarga la página.
    """
    logger.info("Cliente WebSocket conectado")
    state = telemetry_repo.get_state()
    emit("connection_status", {
        "connected": state.connected,
        "port":      state.port,
        "error":     state.error_message,
    })
    # Enviamos el historial para popular las gráficas sin esperar el próximo poll
    _emit_history_to_caller()


@socketio.on("connect_device")
def handle_connect_device(data: dict):
    """
    Evento disparado cuando el usuario hace clic en 'Conectar'.

    data = {'port': 'COM5', 'baudrate': 9600, 'mock': False}

    Flujo:
        1. Detiene cualquier servicio previo (desconexión limpia).
        2. Crea el cliente serial (real o simulado según data['mock']).
        3. Intenta conectar: si falla, notifica el error al cliente.
        4. Crea BuckService con las dependencias y arranca el polling.
        5. Emite el nuevo estado de conexión.
    """
    global buck_service

    port     = str(data.get("port", "COM3")).strip()
    baudrate = int(data.get("baudrate", 9600))
    use_mock = bool(data.get("mock", False))

    logger.info(f"Solicitud de conexión: port={port!r}, baud={baudrate}, mock={use_mock}")

    # Detenemos el servicio anterior si existía (evita dos hilos de polling)
    if buck_service:
        buck_service.stop()
        buck_service = None

    # Elegimos cliente real o simulado según el flag de la UI
    if use_mock:
        client = MockSerialClient()
        display_port = "SIMULACIÓN"
    else:
        client = SerialClient(
            port=port,
            baudrate=baudrate,
            on_disconnect=_on_serial_disconnect,
        )
        display_port = port

    # Intentamos establecer la conexión
    success, error_msg = client.connect()
    if not success:
        telemetry_repo.update_state(connected=False, error_message=error_msg)
        emit("connection_status", {"connected": False, "port": port, "error": error_msg})
        return

    # Construimos el servicio inyectando sus dependencias
    buck_service = BuckService(
        serial_client=client,
        repository=telemetry_repo,
        socketio=socketio,
    )
    buck_service.start_polling()

    telemetry_repo.update_state(connected=True, port=display_port, error_message="")
    telemetry_repo.add_log_entry(f"[CONEXIÓN] Puerto {display_port} abierto a {baudrate} bps")

    # emit() solo al cliente que envió el evento
    emit("connection_status", {"connected": True, "port": display_port, "error": ""})
    # socketio.emit() a TODOS los clientes (ej. otra pestaña abierta)
    socketio.emit("command_log", {"entries": telemetry_repo.get_log()})


@socketio.on("disconnect_device")
def handle_disconnect_device():
    """
    Cierra la conexión serial de forma controlada por solicitud del usuario.
    A diferencia de _on_serial_disconnect, aquí NO disparamos una reconexión.
    """
    global buck_service
    if buck_service:
        buck_service.stop()
        buck_service = None

    telemetry_repo.update_state(connected=False, error_message="")
    telemetry_repo.add_log_entry("[CONEXIÓN] Desconectado por el usuario")

    emit("connection_status", {"connected": False, "port": "", "error": ""})
    socketio.emit("command_log", {"entries": telemetry_repo.get_log()})


@socketio.on("set_voltage")
def handle_set_voltage(data: dict):
    """
    Recibe el setpoint de la UI y lo delega al BuckService para validar y enviar.

    data = {'value': 5.5}
    """
    if not buck_service:
        emit("setpoint_result", {"success": False, "error": "No hay conexión activa"})
        return

    value  = data.get("value")
    result = buck_service.set_voltage(value)

    status_str = "OK" if result["success"] else result.get("error", "ERROR")
    telemetry_repo.add_log_entry(f"[TX] SET V {value} → {status_str}")
    socketio.emit("command_log", {"entries": telemetry_repo.get_log()})
    emit("setpoint_result", result)


@socketio.on("reset_faults")
def handle_reset_faults():
    """Envía RESET al Arduino para limpiar faltas activas (OVERCURRENT, etc.)."""
    if not buck_service:
        emit("reset_result", {"success": False, "error": "No hay conexión activa"})
        return

    result = buck_service.reset_faults()

    status_str = "OK" if result["success"] else result.get("error", "ERROR")
    telemetry_repo.add_log_entry(f"[TX] RESET → {status_str}")
    socketio.emit("command_log", {"entries": telemetry_repo.get_log()})
    emit("reset_result", result)


@socketio.on("request_history")
def handle_request_history():
    """
    El cliente solicita el historial (ej. al reconectar o recargar la página).
    Enviamos solo al cliente que lo pidió, no a todos.
    """
    _emit_history_to_caller()


# ── Helpers internos ──────────────────────────────────────────────────────────

def _emit_history_to_caller() -> None:
    """
    Serializa el historial del repositorio y lo emite con emit() (solo al llamador).
    Los valores None (timeouts) se pasan tal cual; el JS en main.js los filtra.
    """
    history = telemetry_repo.get_history()
    emit("history_data", {
        "timestamps": [r.timestamp for r in history],
        "v_out":      [r.v_out    for r in history],
        "i_out":      [r.i_out    for r in history],
    })


def _on_serial_disconnect() -> None:
    """
    Callback llamado por SerialClient cuando detecta una desconexión inesperada
    (error de IO, cable USB desconectado, HC-05 fuera de rango, etc.).

    Usamos socketio.emit() para notificar a TODOS los navegadores abiertos,
    ya que es una condición de error global del sistema.
    """
    logger.warning("Desconexión inesperada del HC-05 detectada")
    telemetry_repo.update_state(connected=False, error_message="HC-05 desconectado inesperadamente")
    telemetry_repo.add_log_entry("[ERROR] Conexión perdida con HC-05 — esperando reconexión…")

    socketio.emit("connection_status", {
        "connected": False,
        "port":      telemetry_repo.get_state().port,
        "error":     "HC-05 desconectado inesperadamente",
    })
    socketio.emit("command_log", {"entries": telemetry_repo.get_log()})


# ══════════════════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Buck Converter Web Controller")
    parser.add_argument("--port", default="5000", help="Puerto HTTP del servidor web (default: 5000)")
    parser.add_argument("--mock", action="store_true", help="Inicia en modo simulación — no requiere hardware")
    args = parser.parse_args()

    if args.mock:
        logger.info("══ MODO SIMULACIÓN ══ No se requiere HC-05 ni Arduino")

    logger.info(f"Servidor iniciando en http://localhost:{args.port}")
    logger.info("Presiona Ctrl+C para detener")

    # socketio.run() reemplaza app.run() para habilitar WebSockets.
    # allow_unsafe_werkzeug=True: requerido por Flask-SocketIO 5.x con el
    # servidor de desarrollo de Werkzeug (Flask). En producción se usaría gunicorn.
    # host='0.0.0.0' permite acceso desde la red local (ej. tablet o móvil).
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(args.port),
        debug=False,
        allow_unsafe_werkzeug=True,
    )
