/**
 * main.js — Cliente WebSocket + lógica de la interfaz
 *
 * Arquitectura del frontend:
 *   1. socket = io()  →  abre el WebSocket al servidor Flask.
 *   2. Handlers socket.on(...)  →  actualizan la UI cuando llegan datos.
 *   3. Handlers addEventListener(...)  →  emiten eventos cuando el usuario actúa.
 *   4. createChart() / pushChartPoint()  →  gestionan las gráficas Chart.js.
 *
 * Flujo de datos:
 *   [Arduino] → serial_client → buck_service → socketio.emit('telemetry')
 *             → [este archivo] → actualiza DOM + gráficas
 */

'use strict';

// ── Conexión Socket.IO ────────────────────────────────────────────────────────
// io() sin argumentos conecta a la misma URL que sirvió el HTML.
// Socket.IO manejará la reconexión automática si el servidor se reinicia.
// Ref: https://socket.io/docs/v4/client-initialization/
const socket = io();

// ── Estado local ─────────────────────────────────────────────────────────────
let isConnected = false;

// ── Referencias al DOM ───────────────────────────────────────────────────────
const $ = id => document.getElementById(id);   // alias corto para getElementById

const elStatusBadge   = $('status-badge');
const elBtnConnect    = $('btn-connect');
const elBtnDisconnect = $('btn-disconnect');
const elBtnApply      = $('btn-apply');
const elBtnReset      = $('btn-reset');
const elPortInput     = $('port-input');
const elBaudInput     = $('baud-input');
const elMockCheck     = $('mock-check');
const elVoltageSlider = $('voltage-slider');
const elVoltageInput  = $('voltage-input');
const elSliderDisplay = $('slider-display');
const elMeterVout     = $('meter-vout');
const elMeterIout     = $('meter-iout');
const elMeterStatus   = $('meter-status');
const elMeterSetpoint = $('meter-setpoint');
const elCommandLog    = $('command-log');
const elDisplayPort   = $('display-port');
const elDisplayStatus = $('display-conn-status');
const elErrorMsg      = $('error-msg');
const elFeedback      = $('setpoint-feedback');

// ══════════════════════════════════════════════════════════════════════════════
//  GRÁFICAS CHART.JS
// ══════════════════════════════════════════════════════════════════════════════

const MAX_CHART_POINTS = 120;   // 60 s × 2 Hz = 120 puntos máximos

/**
 * Crea una gráfica de línea Chart.js con el tema oscuro de la app.
 *
 * @param {string} canvasId  - ID del <canvas> en el HTML
 * @param {string} label     - Etiqueta mostrada en la leyenda
 * @param {string} color     - Color CSS de la línea (ej. '#00d4ff')
 * @param {number} yMax      - Límite superior del eje Y
 *
 * Opciones clave:
 *   animation: false  →  sin animación en cada update (esencial para tiempo real)
 *   pointRadius: 0    →  sin círculos en cada punto (mejora el rendimiento)
 *   fill: true        →  área bajo la curva rellena con color semitransparente
 *   tension: 0.3      →  curva suavizada (0 = recta, 1 = muy curva)
 */
function createChart(canvasId, label, color, yMax) {
    const ctx = $(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],         // eje X: timestamps como strings HH:MM:SS
            datasets: [{
                label,
                data: [],
                borderColor:     color,
                backgroundColor: color + '1a',   // color con ~10% opacidad
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,                   // CRÍTICO: sin esto el scroll suavizado ralentiza la UI
            plugins: {
                legend: {
                    display: false              // usamos chart-label del HTML en su lugar
                },
                tooltip: {
                    backgroundColor: '#161b22',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    titleColor: '#8b949e',
                    bodyColor: '#c9d1d9',
                    callbacks: {
                        // Añade la unidad al tooltip (ej. "5.23 V")
                        label: ctx => `${ctx.parsed.y.toFixed(2)} ${yMax <= 3 ? 'A' : 'V'}`
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#8b949e',
                        font: { size: 10 },
                        maxTicksLimit: 7,       // no más de 7 etiquetas en el eje X
                        maxRotation: 0,
                    },
                    grid: { color: '#1c2128' }
                },
                y: {
                    min: 0,
                    max: yMax,
                    ticks: { color: '#8b949e', font: { size: 10 } },
                    grid: { color: '#1c2128' }
                }
            }
        }
    });
}

// Inicializamos las dos gráficas (se crean vacías, se llenan con los eventos)
const chartVout = createChart('chart-vout', 'V_out (V)', '#00d4ff', 10);
const chartIout = createChart('chart-iout', 'I_out (A)', '#39d353', 3);

/**
 * Agrega un nuevo punto a una gráfica y descarta el más antiguo si supera MAX_CHART_POINTS.
 * Implementa el buffer circular del lado del cliente.
 *
 * chart.update('none') redibuja sin animación de transición.
 */
function pushChartPoint(chart, timeLabel, value) {
    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(value);

    if (chart.data.labels.length > MAX_CHART_POINTS) {
        chart.data.labels.shift();              // elimina el primer elemento (más antiguo)
        chart.data.datasets[0].data.shift();
    }
    chart.update('none');
}

// ══════════════════════════════════════════════════════════════════════════════
//  HANDLERS DE SOCKET.IO — Servidor → Cliente
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Evento 'telemetry': llega cada 500 ms mientras hay conexión activa.
 * Actualiza los medidores digitales, el indicador de estado y las gráficas.
 *
 * data = { v_out: 5.23, i_out: 0.87, status: 'OK', timestamp: 1716000000, setpoint: 5.0 }
 */
socket.on('telemetry', data => {
    // Formateamos el timestamp Unix a HH:MM:SS local para el eje X
    const time = new Date(data.timestamp * 1000).toLocaleTimeString('es-PE');

    // ── Medidores digitales ───────────────────────────────────────────────
    elMeterVout.textContent = data.v_out != null
        ? `${data.v_out.toFixed(2)} V` : '— V';
    elMeterIout.textContent = data.i_out != null
        ? `${data.i_out.toFixed(2)} A` : '— A';
    elMeterSetpoint.textContent = `${data.setpoint.toFixed(1)} V`;

    // ── Indicador de estado con color semántico ───────────────────────────
    elMeterStatus.textContent = data.status;
    // Resetea clases de color anteriores antes de aplicar la nueva
    elMeterStatus.className = 'meter-value';
    switch (data.status) {
        case 'OK':          elMeterStatus.classList.add('status-ok');      break;
        case 'OVERCURRENT':
        case 'OVERVOLTAGE': elMeterStatus.classList.add('status-fault');   break;
        case 'DCM':         elMeterStatus.classList.add('status-dcm');     break;
        default:            elMeterStatus.classList.add('status-unknown'); break;
    }

    // ── Gráficas: solo añadimos el punto si el valor no es null ──────────
    if (data.v_out != null) pushChartPoint(chartVout, time, data.v_out);
    if (data.i_out != null) pushChartPoint(chartIout, time, data.i_out);
});

/**
 * Evento 'connection_status': llega al conectar, desconectar o ante errores.
 * data = { connected: bool, port: string, error: string }
 */
socket.on('connection_status', data => {
    isConnected = data.connected;
    _updateConnectionUI(data.connected, data.port, data.error);
});

/**
 * Evento 'history_data': historial de los últimos 60 s.
 * Llega al conectar la UI o al emitir 'request_history'.
 * Recargamos las gráficas completas con los datos del servidor.
 *
 * data = { timestamps: [...], v_out: [...], i_out: [...] }
 */
socket.on('history_data', data => {
    // Limpiamos las gráficas antes de volcar el historial
    [chartVout, chartIout].forEach(ch => {
        ch.data.labels = [];
        ch.data.datasets[0].data = [];
    });

    data.timestamps.forEach((ts, i) => {
        const time = new Date(ts * 1000).toLocaleTimeString('es-PE');
        if (data.v_out[i] != null) {
            chartVout.data.labels.push(time);
            chartVout.data.datasets[0].data.push(data.v_out[i]);
        }
        if (data.i_out[i] != null) {
            chartIout.data.labels.push(time);
            chartIout.data.datasets[0].data.push(data.i_out[i]);
        }
    });

    chartVout.update('none');
    chartIout.update('none');
});

/**
 * Evento 'command_log': lista de las últimas 20 líneas del log TX/RX.
 * data = { entries: ['[12:00:01] [TX] SET V 5.5 → OK', ...] }
 */
socket.on('command_log', data => {
    elCommandLog.innerHTML = '';
    data.entries.forEach(entry => {
        const div = document.createElement('div');
        div.className = 'log-entry';
        div.textContent = entry;
        elCommandLog.appendChild(div);
    });
    // Scroll automático al final: el usuario siempre ve la entrada más reciente
    elCommandLog.scrollTop = elCommandLog.scrollHeight;
});

/**
 * Resultado de 'set_voltage': muestra feedback temporal al usuario.
 * data = { success: bool, error?: string }
 */
socket.on('setpoint_result', data => {
    _showFeedback(data.success, data.success ? 'Setpoint aplicado correctamente' : data.error);
});

/**
 * Resultado de 'reset_faults'.
 */
socket.on('reset_result', data => {
    _showFeedback(data.success, data.success ? 'Faltas limpiadas — sistema rearmed' : data.error);
});

// ══════════════════════════════════════════════════════════════════════════════
//  HANDLERS DE EVENTOS DOM — Usuario → Servidor
// ══════════════════════════════════════════════════════════════════════════════

elBtnConnect.addEventListener('click', () => {
    const port     = elPortInput.value.trim();
    const baudrate = parseInt(elBaudInput.value, 10);
    const mock     = elMockCheck.checked;

    if (!port && !mock) {
        _showError('Ingresa un puerto serial o activa el modo simulación');
        return;
    }
    _hideError();
    // Emitimos el evento al servidor; la respuesta llega por 'connection_status'
    socket.emit('connect_device', { port, baudrate, mock });
});

elBtnDisconnect.addEventListener('click', () => {
    socket.emit('disconnect_device');
});

elBtnApply.addEventListener('click', () => {
    const value = parseFloat(elVoltageInput.value);
    if (isNaN(value) || value < 0 || value > 9) {
        _showFeedback(false, 'Valor fuera de rango: debe estar entre 0.0 y 9.0 V');
        return;
    }
    socket.emit('set_voltage', { value });
});

elBtnReset.addEventListener('click', () => {
    socket.emit('reset_faults');
});

// ── Sincronización bidireccional slider ↔ input numérico ─────────────────────
// Cuando el slider cambia, actualizamos el input numérico (y el display),
// y viceversa. Esto mantiene ambos controles siempre sincronizados.

elVoltageSlider.addEventListener('input', () => {
    const val = parseFloat(elVoltageSlider.value).toFixed(1);
    elSliderDisplay.textContent = val;
    elVoltageInput.value = val;
});

elVoltageInput.addEventListener('input', () => {
    const val = parseFloat(elVoltageInput.value);
    if (!isNaN(val) && val >= 0 && val <= 9) {
        elVoltageSlider.value = val;
        elSliderDisplay.textContent = val.toFixed(1);
    }
});

// ── Checkbox de modo simulación: deshabilita el campo de puerto ───────────────
elMockCheck.addEventListener('change', () => {
    elPortInput.disabled = elMockCheck.checked;
    if (elMockCheck.checked) {
        elPortInput.value = '';
        elPortInput.placeholder = 'Puerto no requerido en modo simulación';
    } else {
        elPortInput.placeholder = 'COM3 · /dev/rfcomm0';
    }
});

// ══════════════════════════════════════════════════════════════════════════════
//  FUNCIONES AUXILIARES DE UI
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Actualiza todos los elementos de UI que dependen del estado de conexión.
 *
 * @param {boolean} connected  - ¿Hay conexión activa?
 * @param {string}  port       - Puerto conectado (vacío si desconectado)
 * @param {string}  error      - Mensaje de error (vacío si sin error)
 */
function _updateConnectionUI(connected, port, error) {
    // Badge del header
    elStatusBadge.textContent = connected ? 'CONECTADO' : 'DESCONECTADO';
    elStatusBadge.className = connected
        ? 'badge badge-connected'
        : 'badge badge-disconnected';

    // Info panel de conexión
    elDisplayPort.textContent   = port || '—';
    elDisplayStatus.textContent = connected ? 'Conectado' : 'Sin conexión';

    // Habilitación/deshabilitación de botones
    elBtnConnect.disabled    = connected;
    elBtnDisconnect.disabled = !connected;
    elBtnApply.disabled      = !connected;
    elBtnReset.disabled      = !connected;

    if (error) {
        _showError(error);
    } else {
        _hideError();
    }
}

function _showError(msg) {
    elErrorMsg.textContent = '⚠ ' + msg;
    elErrorMsg.className = 'alert alert-error';
    elErrorMsg.style.display = 'block';
}

function _hideError() {
    elErrorMsg.style.display = 'none';
}

/**
 * Muestra un mensaje de feedback temporal (desaparece tras 3.5 s).
 * Reutilizable para setpoint y reset.
 *
 * @param {boolean} success - True → mensaje verde, False → mensaje rojo
 * @param {string}  message - Texto a mostrar
 */
function _showFeedback(success, message) {
    elFeedback.textContent = (success ? '✓ ' : '⚠ ') + message;
    elFeedback.className = 'alert ' + (success ? 'alert-success' : 'alert-error');
    elFeedback.style.display = 'block';

    // Cancelamos el timer anterior si el usuario aplica dos setpoints rápido
    clearTimeout(elFeedback._hideTimer);
    elFeedback._hideTimer = setTimeout(() => {
        elFeedback.style.display = 'none';
    }, 3500);
}
