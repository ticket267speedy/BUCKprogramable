# Guía completa — Buck programable: cálculos y selección de componentes

> Documento de trabajo para que entiendas cada paso del diseño del buck antes de comprar en Paruro. Se basa en Mohan/Undeland/Robbins *Power Electronics* cap. 7, Erickson/Maksimović *Fundamentals of Power Electronics* cap. 2, y la nota de aplicación TI **SLVA477B**. Todas las fórmulas de tu compañero se derivan abajo desde la física.

---

## 0. El problema en una sola figura mental

Tienes una fuente DC de 12 V y quieres una salida DC variable (programable) entre ≈0 V y 9 V (o 12 V) que la lógica del Arduino fije. Para no quemar energía como lo haría un regulador lineal, **conmutas** un transistor a alta frecuencia: cuando el switch está cerrado, la fuente alimenta una bobina; cuando se abre, la bobina descarga su energía hacia la carga a través de un diodo. El **filtro LC** "promedia" esos pulsos y deja un nivel DC limpio en la salida. Cuánto vale ese DC depende **exclusivamente** de qué fracción del periodo dejaste cerrado el switch — eso es el **ciclo de trabajo (duty cycle, D)**.

```
      SW (MOSFET)        L (bobina)
12V o---/\----+----o          o----+----+----o Vo
              |   diodo            |    |
              |    |               |    |
              v    v               |    |
             (-) (-) GND          Cout  Rload
                                   |    |
                                  GND  GND
```

Esa es toda la idea. El resto del diseño es elegir L, C, switch, diodo y la lógica de control para que el promedio sea exactamente el que pides y el rizado sea pequeño.

---

## 1. Diccionario de variables (la fuente de tu confusión)

Tu compañero mezcla la notación de Mohan con notación de control. Aquí los significados, **uno por uno**:

| Símbolo | Qué es | Cómo se llama también |
|---|---|---|
| **Vd** | **V**oltaje DC de la fuente (input). Mohan usa "d" de *direct* (DC). | Vin, VIN, V_input |
| **Vo** | Voltaje DC promedio de salida (lo que mide un multímetro). | Vout, VOUT |
| **vo(t)** | Forma de onda instantánea de salida (con rizado). Vo es su promedio. | — |
| **iL(t)** | Corriente instantánea por la bobina (es triangular). | — |
| **IL, Io** | Promedio de iL. En CCM coincide con la corriente de carga DC. | Iout |
| **Ts** | **T**iempo del periodo de **s**witching. Ts = ton + toff. | T |
| **fs** | Frecuencia de switching = 1/Ts. | fsw |
| **D** | **D**uty cycle = ton / Ts. Es un número entre 0 y 1. | ciclo de trabajo |
| **ΔIL** | Rizado pico-a-pico de iL (alto del triángulo). | inductor ripple |
| **ΔVo** | Rizado pico-a-pico del voltaje de salida. | output ripple |
| **ILB** | Corriente promedio en la **B**oundary entre CCM y DCM (frontera). | I_crítica |
| **Vref** | **V**oltaje de **ref**erencia: la "consigna" — el valor de Vo que TÚ pides. En tu proyecto sale del potenciómetro/Arduino. | setpoint, Vdeseado |
| **Vcontrol** | Voltaje analógico que entrega el amplificador de error después de comparar Vref con Vo medido. Manda el PWM. | control signal, output del compensador |
| **V̂st** | Pico (sombrero = "hat" = max) de la onda **s**aw**t**ooth (diente de sierra) interna del modulador PWM. | V̂ramp |
| **η** | Eficiencia del convertidor (0.85 a 0.95 típicamente). | efficiency |

> **Lección clave**: cuando lees "Vref" en los apuntes de tu compañero, piensa: *"este es el voltaje que YO le digo al sistema que quiero a la salida"*. En tu proyecto programable, Vref es la salida del DAC/potenciómetro del Arduino. El término "referencia" viene de la teoría de control: es la referencia contra la que comparas la salida real.

---

## 2. Por qué la salida vale Vo = D · Vd (la fórmula fundamental)

Esta es la columna vertebral del buck. Voy a derivarla paso a paso como aparece en Mohan §7-3:

**Mientras el switch está cerrado (durante ton = D·Ts)**:
- El nodo de switching está a Vd.
- El voltaje sobre la bobina: vL = Vd − Vo.
- Como vL > 0, la corriente en L sube linealmente. Pendiente = (Vd − Vo)/L.

**Mientras el switch está abierto (durante toff = (1−D)·Ts)**:
- La bobina no puede cambiar su corriente bruscamente (regla "el flujo no salta"), entonces fuerza al diodo Schottky a conducir.
- El nodo de switching queda a ≈0 V (suelo, vía diodo).
- vL = 0 − Vo = −Vo.
- Como vL < 0, la corriente en L baja linealmente. Pendiente = −Vo/L.

**Condición de régimen permanente (steady state)**:
La corriente en L empieza el periodo igual que como termina (si no, estaría creciendo o decreciendo cada ciclo, lo cual no es estado estable). Esto se llama **volt-second balance**: el área positiva = área negativa sobre el inductor en un periodo.

$$ (V_d - V_o)\cdot D\cdot T_s \;=\; V_o \cdot (1-D)\cdot T_s $$

Resolviendo para Vo:

$$ \boxed{V_o = D \cdot V_d} $$

**De aquí D = Vo/Vd**. Tu pregunta — *"D es Vo/Vi?"* — la respuesta corta es **sí, en el caso ideal CCM**. En TI SLVA477B aparece con eficiencia: D = Vo/(Vd·η). Eso solo "infla" D un poquito para compensar las pérdidas reales.

---

## 3. Tu pregunta crítica: ¿cómo puede un L y C **fijos** servir para cualquier D?

Esta es la pregunta más importante y casi nadie te la responde directamente. Hay que pensarlo así:

El L y C **NO** se "sintonizan" a un valor de D. Lo que hacen es formar un **filtro paso-bajos** entre la señal cuadrada del switch (que tiene componentes a fs y sus armónicos) y la carga. El requerimiento es solo uno:

$$ f_c = \frac{1}{2\pi\sqrt{LC}} \;\ll\; f_s $$

Es decir, la frecuencia de corte del filtro tiene que estar **muy por debajo** de la frecuencia de switching. Si eso se cumple, el filtro deja pasar el promedio (DC) y bloquea el "ruido" a fs.

**Lo que SÍ cambia con D**:
- El nivel DC de salida cambia: Vo = D·Vd. Es exactamente lo que quieres — esa es la "perilla" que ajustas para programar la salida.
- El **rizado pico-a-pico** ΔIL del inductor cambia. Es máximo en D = 0.5 (lo demostramos en §4).

**Lo que NO cambia con D**:
- La capacidad del filtro de promediar el cuadrado y dejar DC limpio.
- Su frecuencia de corte natural.

**Analogía**: un altavoz reproduce desde 20 Hz hasta 20 kHz. No "se reconfigura" para cada nota. Es un componente lineal que responde a cualquier entrada en su banda. El LC del buck es lo mismo: una vez diseñado, funciona en todo el rango.

**Lo que SÍ tienes que asegurar**:
1. Que en el **peor caso de D**, el rizado ΔIL no supere tu límite (por eso el compañero pone D=0.5 en sus cálculos).
2. Que la corriente promedio Io no baje de **ILB** (el límite de modo continuo), salvo que aceptes operar en modo discontinuo, que cambia las fórmulas y empeora la regulación.

---

## 4. Derivación de las fórmulas que escribió tu compañero (Mohan eqs. 7-22 a 7-25)

### 4.1 Rizado de corriente en el inductor (ΔIL)

Durante toff, la corriente baja con pendiente Vo/L durante un tiempo (1−D)·Ts. El alto del triángulo (pico-a-pico) es:

$$ \boxed{\Delta I_L = \frac{V_o\,(1-D)\,T_s}{L}} \quad \text{(Mohan eq. 7-22)} $$

Esta es la fórmula del "Power Electronics with Dr. K" del YouTube. Sustituyendo Vo = D·Vd:

$$ \Delta I_L = \frac{D\,V_d\,(1-D)\,T_s}{L} = \frac{D(1-D)\,V_d\,T_s}{L} $$

La función **D(1−D)** es una parábola con máximo en D=0.5, donde vale 0.25. **Por eso el peor caso de rizado es D=0.5**. En ese punto:

$$ \Delta I_{L,\text{max}} = \frac{V_d\,T_s}{4L} $$

> Cuando tu compañero escribe "*peor caso D=0.5 → Vo=6V*", está usando precisamente este hecho: con Vd=12 V el peor rizado ocurre cuando la salida está a la mitad. En la práctica tu salida va a estar la mayor parte del tiempo lejos de 6 V (al usuario le interesa 5 V, 3.3 V, 9 V, etc.), pero hay que diseñar para el caso más exigente.

### 4.2 Por qué se usa "30 % de rizado típico"

Industrialmente se elige ΔIL / Io entre 20 % y 40 % (TI SLVA477B eq. 20, Analog Devices, ROHM). Tu compañero eligió 30 %. ¿Por qué este rango?

- **Si bajas el rizado** (ej. 10 %): necesitas L grande → caro, físicamente grande, ESR del bobinado sube → más pérdidas, más caída.
- **Si subes el rizado** (ej. 60 %): L pequeño y barato, pero:
  - El switch y el diodo ven picos de corriente mayores → caen sus márgenes.
  - El filtro de salida necesita C grande para no dejar ruido.
  - El núcleo del inductor puede saturar.

20-40 % es el "sweet spot" reportado por las app notes. **Referencia: Analog Devices "Selecting the Right Inductor Current Ripple"**.

### 4.3 Selección de L

Despejando L de la fórmula del rizado en el peor caso:

$$ \boxed{L = \frac{V_d\,T_s}{4\,\Delta I_{L,\text{max}}}} $$

**Sustituyendo tus números**:
- Vd = 12 V
- Ts = 32 µs (porque fs = 31.25 kHz — esta es la frecuencia máxima cómoda del PWM de Arduino UNO/Nano con prescaler de 1 en el Timer1)
- Io_nom = 2 A, rizado 30 % → ΔIL_max = 0.6 A

$$ L = \frac{12 \times 32 \times 10^{-6}}{4 \times 0.6} = \frac{384 \times 10^{-6}}{2.4} = 160 \,\mu\text{H} $$

Coincide exactamente con lo que escribió tu compañero. Como **160 µH no es un valor estándar comercial común**, escogió el siguiente valor estándar disponible (180 ó 220 µH). Con 220 µH:

$$ \Delta I_L = \frac{12 \times 32 \times 10^{-6}}{4 \times 220 \times 10^{-6}} = 0.436 \,\text{A} \;\;(\approx 21.8\%) $$

Mejor todavía: rizado menor. Por eso eligió 220 µH como definitivo.

### 4.4 Selección de C (cálculo del rizado de voltaje)

La corriente triangular del inductor entra al paralelo C ∥ Rload. La parte AC del triángulo va casi toda al capacitor (porque tiene impedancia mucho menor a fs que Rload). Integrando la parte positiva del triángulo (carga del cap) se llega a la fórmula de Mohan eq. 7-24:

$$ \boxed{\frac{\Delta V_o}{V_o} = \frac{T_s^2\,(1-D)}{8\,L\,C}} = \frac{(1-D)}{8\,L\,C\,f_s^2} $$

Para ΔVo/Vo = 5 % en peor caso D=0.5, con L=220 µH y fs=31.25 kHz:

$$ 0.05 = \frac{(1-0.5)}{8 \times 220\times10^{-6} \times C \times (31250)^2} $$

Despejando:

$$ C = \frac{0.5}{8 \times 0.05 \times 220\times10^{-6} \times (31250)^2} = 5.82 \,\mu\text{F} $$

Igual al cálculo del compañero. Por margen y por la realidad de los electrolíticos (capacidad nominal con ±20 %, pérdida con temperatura/edad), **escoges ≥10 µF**. La nota dice "10 µF que resista 25 V" — eso es porque el cap debe aguantar picos de Vin (12 V) con margen 2×.

### 4.5 Corriente de frontera ILB (continuo vs. discontinuo) — eq. 7-25

Si la corriente promedio Io baja demasiado, el triángulo de iL toca cero durante toff: ahí entra el **modo de conducción discontinua (DCM)** y Vo deja de seguir D·Vd (pasa a depender de la carga). Queremos siempre estar en **CCM**.

La corriente promedio mínima para mantener CCM es:

$$ \boxed{I_{LB} = \frac{D\,T_s\,(V_d - V_o)}{2L} = \frac{D(1-D)\,V_d\,T_s}{2L}} $$

En el peor caso D = 0.5 con L = 220 µH:

$$ I_{LB} = \frac{0.5 \times 0.5 \times 12 \times 32\times10^{-6}}{2 \times 220\times10^{-6}} = 0.218 \,\text{A} = 218\,\text{mA} $$

**Interpretación**: si tu carga consume **menos de 218 mA**, el buck entra en DCM. Por eso tu compañero dice "*la carga debe consumir más de 220 mA*" o, equivalente, "*Rmax = 6 V / 0.22 A ≈ 27.3 Ω*". Más allá de esa resistencia, ya no estás en CCM y las fórmulas anteriores **dejan de aplicar** rigurosamente.

> En la práctica esto importa: si tu usuario pide 9 V pero no conecta nada (o conecta solo un voltímetro de 10 MΩ), estás en DCM extremo. Tu lazo cerrado tiene que tolerarlo o avisar. Una solución clásica es poner una **carga "preload"** fija (ej. 1 kΩ a 9 V → 9 mA, no soluciona el problema pero amortigua) o aceptar DCM y compensar con lazo cerrado robusto.

---

## 5. El lazo cerrado y dónde aparece Vref

Tu compañero escribe `Vcontrol = K · Verror` y `Vo lo podemos poner en función de Vref`. La cadena de control es:

```
 Vref (lo que pides)
   |
   v
  [+] -------> [Amplificador de error] --> Vcontrol -->[Comparador con dientes de sierra V̂st] --> PWM (D = Vcontrol/V̂st)
   ^                                                                                            |
   |                                                                                            v
 Vo_real <----- [divisor de tensión] <--- Vo (salida del buck) <--- [Buck: Vo = D·Vd] <--------+
```

Pieza por pieza:

1. **Vref** es la consigna. Si quieres 5 V de salida y tu divisor de medición divide por 3, Vref = 5/3 V. (En tu proyecto Vref lo fija el Arduino vía un DAC o PWM filtrado.)
2. **Verror = Vref − Vo_real** (Vo_real es la versión escalada de Vo, pasada por el divisor de tensión).
3. **Vcontrol = K·Verror** (el "K" es la ganancia del amplificador de error / compensador; para que el lazo sea estable suele ser un PI o PID, no solo proporcional).
4. **Comparador**: PWM compara Vcontrol contra una onda triangular/diente-de-sierra de amplitud V̂st a frecuencia fs. La salida es alta mientras Vcontrol > onda. Eso produce D = Vcontrol / V̂st (relación lineal del modulador).
5. **Buck**: con esa D, la planta entrega Vo = D·Vd.

**Sustituyendo D**: Vo = (Vcontrol / V̂st) · Vd. Por eso tu compañero escribe **Vo/Vd = Vcontrol/V̂st**.

> Para tu proyecto en Arduino, esta cadena se simplifica: el ADC mide Vo (vía divisor), el código compara con Vref (un número en software, no un voltaje físico), calcula el error, lo procesa por PI/PID, y la salida del PI/PID se manda al PWM (analogWrite o registro OCR del Timer1). El "comparador con diente de sierra" lo hace internamente el Timer del AVR.

---

## 6. "Nominal", eficiencia, y dimensionamiento

**Nominal** = el valor "de placa" o "de diseño" en condición normal de operación. No es máximo ni mínimo, es el punto típico. Para tu buck:

- **Vout nominal**: el punto medio (~6 V) o el más usado (5 V).
- **Iout nominal**: el compañero asume **2 A**. ¿De dónde viene? Lo establecimos como objetivo de proyecto. Lo importante es que **fija el tamaño del L, C, MOSFET, diodo y fusible**.
- **Potencia nominal**: P = Vo·Io. A 9 V × 2 A = 18 W nominal. A 5 V × 2 A = 10 W.

**Eficiencia esperada η**:
- Buck síncrono con MOSFETs grandes en alta corriente: 92-97 %.
- Tu buck **no es síncrono** (usas un diodo Schottky en lugar de un segundo MOSFET). El diodo siempre cae ≈0.4-0.55 V, lo que limita la eficiencia, sobre todo a Vo bajo.
- Con un 1N5822 (1 A continuo, no muy rápido) en CCM, podemos esperar realistamente **η ≈ 85-90 %** a 1-2 A.
- Si necesitaras > 95 % tendrías que reemplazar el diodo por un MOSFET de "lado bajo" (sync rectifier).

> **Para tu compra**: si llegas a > 90 % está excelente para un proyecto educativo. No es razón para sobre-invertir en componentes premium.

---

## 7. Selección de componentes — qué pedir en Paruro

### 7.1 Inductor — el componente más crítico

**Lo que pides**: bobina de **220 µH, ≥ 3 A saturación, núcleo ferrita o iron-powder, baja DCR**.

| Parámetro | Valor mínimo | Por qué |
|---|---|---|
| Inductancia | 220 µH (acepta 180-330) | Para mantener rizado < 30 % a 2 A |
| Corriente de saturación (Isat) | **≥ 3 A** | Tu pico de corriente es Io + ΔIL/2 ≈ 2 + 0.22 = 2.22 A. Margen 35 % mínimo. Saturar el núcleo es lo PEOR — la L cae en picado y el switch ve un cortocircuito. |
| Corriente RMS continua | ≥ 2.5 A | Para calentamiento sostenido. |
| DCR (resistencia DC del bobinado) | Lo más baja posible (< 200 mΩ) | Cada miliohm es pérdida directa P = I²·R. A 2A, 100 mΩ = 0.4 W perdidos. |
| Núcleo | Ferrita toroidal o blindado | Toroide irradia poco campo magnético, no interfiere con tu OLED ni con el ADC del Arduino. |
| Frecuencia útil | ≥ 100 kHz nominal | Para que su modelo SPICE-like sea válido a 31 kHz. |

**Alternativas comunes en Paruro y qué hacer si no encuentras**:

- **No hay 220 µH con 3A**: prueba 100 µH con ≥4A o 330 µH con ≥2.5A. Si el L sube, ΔIL baja y todo mejora; si el L baja, ΔIL sube y debes rehacer cálculos. Si compras 100 µH, ΔIL ≈ 0.96 A (≈48 %) — feo, casi en límite. Mejor 330 µH → ΔIL ≈ 0.29 A (14 %, excelente).
- **Solo hay inductores de núcleo "abierto" (axiales tipo resistor)**: úsalos pero aléjalos físicamente de partes sensibles. No es lo ideal por EMI.
- **Solo hay choques toroidales de fuente de PC (los amarillos)**: son iron-powder, núcleo "polvo de hierro". Generalmente excelentes hasta unos pocos amperios. Mide su inductancia con un LCR si la tienda tiene; si no, calcula por número de vueltas (formulario en cualquier libro de bobinas).
- **Improvisado**: puedes bobinar tú mismo en un toroide AMIDON T-50-26 o similar (núcleo iron-powder amarillo) — pero esto es plan B si no encuentras nada.

> **Regla de bolsillo para Paruro**: si dudas, compra **dos valores** (ej. 220 µH y 330 µH) — son baratos. En la protoboard prueba cuál te da menos rizado de salida (medido con osciloscopio) y elige.

### 7.2 Capacitor de salida — el segundo más crítico

**Lo que pides**: **10 µF mínimo, 25 V mínimo, ESR baja, electrolítico de baja impedancia o cerámico**.

| Parámetro | Valor | Por qué |
|---|---|---|
| Capacidad | ≥ 10 µF (idealmente 22-47 µF) | Margen sobre 5.82 µF calculado, considerando pérdida con DC bias y temperatura. |
| Tensión | ≥ 25 V (2× Vin) | Si el Arduino arranca con la salida descalibrada podría ver picos. Tensión de margen también extiende vida útil. |
| ESR (resistencia serie equivalente) | < 100 mΩ idealmente | ESR añade rizado extra: ΔVo_ESR = ESR·ΔIL. A 0.44 A de rizado, 100 mΩ son 44 mV → bien. 1 Ω serían 440 mV → desastre. |
| Tipo | **Electrolítico aluminio "low ESR"** o cerámico X5R/X7R | Los electrolíticos "estándar" de fuente vieja tienen ESR alta. Los marcados "low impedance" (Nichicon PW/PM, Rubycon ZL/YXF, Panasonic FC/FM) son los buenos. |
| Frecuencia | Buen comportamiento a ≥ 50 kHz | Mira la "impedance vs frequency" del datasheet si existe. |

**Sugerencia práctica**: pon **1 electrolítico de 47 µF/25V low-ESR EN PARALELO con 1 cerámico de 1 µF/50V**. El electro guarda mucha energía, el cerámico cancela picos rápidos (donde el electro fracasa por su inductancia parasitaria ESL). Esto es **estándar industrial** y se llama "tanque dual" o "split capacitor bank".

### 7.3 Capacitor de entrada

**10-47 µF electrolítico /25V + 100 nF cerámico** en paralelo, lo más cerca posible del Drain del MOSFET. **Función**: absorber los picos de corriente pulsantes que el buck demanda de la fuente; sin él, la fuente "ve" un transitorio brutal cada vez que el switch conduce, lo que mete ruido a todo el sistema (incluso al ADC del Arduino que mide Vo).

### 7.4 MOSFET — IRF9540 (Canal P) vs IRF4905

Ya está decidido: **IRF9540** o **IRF4905**. Ambos canal P. La razón de canal P en lugar de N es la simplicidad del gate drive (la fuente del P-MOSFET está conectada a Vd=12 V, así que para encenderlo solo necesitas bajar el gate a 0 V; con un N-MOSFET necesitarías un "bootstrap" o gate driver que genere voltaje por encima de Vd, complicado).

Comparativa rápida:

| Parámetro | IRF9540 | IRF4905 | Necesario |
|---|---|---|---|
| VDSmax | -100 V | -55 V | > 30 V (con margen vs 12 V + ringing) |
| ID continuo | 19 A @ 25°C | 74 A @ 25°C | ≥ 5 A |
| RDS(on) | 117 mΩ @ VGS=-10V | 20 mΩ @ VGS=-10V | menos = mejor |
| VGS(th) | -2 a -4 V | -2 a -4 V | menor que -5 V para encender desde Arduino con 6N137 |

**Veredicto**: IRF4905 es **muy superior** (5× menos RDS(on) → 5× menos pérdida en conducción). En tu corriente nominal (2A):
- IRF9540: P_cond = I²·RDS·D = 4·0.117·0.5 = 0.234 W (manejable sin disipador)
- IRF4905: P_cond = 4·0.020·0.5 = 0.040 W (despreciable)

Si están al mismo precio en Paruro, **compra IRF4905**. Si solo hay IRF9540, sirve perfecto.

> **Importante**: el IRF9540 / IRF4905 son MOSFETs "estándar level" — necesitan VGS de -10 V para entrar bien en zona de saturación. Tu gate driver (optoacoplador 6N137 + transistor NPN 2N2222) debe poder cerrar el gate al GND (0 V respecto a source = -12 V respecto a Vd, lo que enciende fuertemente). Si solo lo llevas a 5 V (es decir VGS = -7 V), el MOSFET conduce pero con RDS(on) más alta y se calienta. Más sobre el gate drive en una sección posterior.

### 7.5 Diodo Schottky — 1N5822

| Parámetro | 1N5822 | Necesario |
|---|---|---|
| If avg | 3 A | ≥ 2 A (margen 50 %) |
| VRRM (reverse) | 40 V | > 20 V |
| Vf forward | ≈ 0.4-0.55 V @ 3A | bajo = mejor |
| Recovery | "fast" (Schottky → ≈ns) | crítico a 31 kHz |

**Veredicto**: perfecto. Compra 1N5822. Alternativas si no hay: **SB540** (5A), **MBR340** (3A), **SR360** (3A). Evita 1N4007 (es rectificador estándar, no Schottky → demasiado lento y Vf más alto).

### 7.6 Divisor de tensión para realimentar al ADC

Tu Vo va hasta 12 V. El ADC de Arduino UNO acepta máximo 5 V (5 V con Vref interno). Por seguridad limita a ≈4 V en el ADC para tener cabeza al pico transitorio.

Diseño: si Vo = 12 V debe verse como 4 V en el ADC → divisor 12/4 = 3:1, es decir R1=20 kΩ + R2=10 kΩ (cualquier proporción 2:1 sirve). Considera:

- Corriente por el divisor: 12 V / (R1+R2) = 12 V / 30 kΩ = 400 µA. Despreciable.
- Pero **no uses divisor muy resistivo** (ej. 200 k + 100 k), porque el ADC del AVR necesita impedancia de fuente ≤ 10 kΩ idealmente. Solución estándar: pon **un cap cerámico de 100 nF al GND en el medio del divisor** para que actúe como "tank" para el sample-and-hold del ADC.

Valores sugeridos: **R1 = 22 kΩ, R2 = 10 kΩ** (con cualquier tolerancia 1 % si los encuentras; si solo hay 5 % no pasa nada porque calibras por software).

### 7.7 Fusible

P max ≈ Vd · Iin_max. En el buck Iin ≈ Iout · D + ΔIL_pico. En peor caso Iout=2A, D=0.5 → Iin ≈ 1 A continuo. Pero con transitorios y arranque puedes ver 2× eso.

**Fusible recomendado**: **2-3 A "fast-blow" tipo F2.5A** en línea de +12 V antes del MOSFET. Sirve como protección, no como precisión. Compra **3 ó 4** porque si pruebas un cortocircuito por accidente quemas uno (es lo normal).

### 7.8 Otros componentes que vas a comprar

| Item | Valor | Propósito |
|---|---|---|
| Resistor de gate (MOSFET) | 22-100 Ω, 1/4 W | Limita di/dt en el gate (evita ringing por inductancia parásita del cable). Empieza con **47 Ω**. |
| Pull-up del gate del IRF9540 | 10 kΩ a Vd | **Crítico**: asegura que el MOSFET esté **apagado** (VGS = 0) cuando el Arduino aún no arranca o se resetea. Sin este resistor, podrías energizar con el gate flotando y el MOSFET en zona lineal → quemado. |
| Resistor de pull-up para 6N137 | 1-4.7 kΩ a 5 V | El 6N137 tiene salida open-collector, **necesita pull-up** o no entrega niveles digitales. Usa **2.2 kΩ** para responder rápido al PWM. |
| Cap. desacople 6N137 | 100 nF cerámico entre VCC y GND del opto | Estándar para cualquier IC digital. |
| Resistor de la base del 2N2222 | 1 kΩ típico | Limita corriente de base. Calcúlalo: VBE ≈ 0.7 V, Iin a 5V/1kΩ = (5-0.7)/1k ≈ 4 mA, con β=100 → Ic ≈ 400 mA (más que suficiente). |

---

## 8. Tu lista consolidada para Paruro

Llevándote lo crítico primero y alternativas en paréntesis:

**Etapa de potencia**:
- [ ] **MOSFET IRF4905** ×1 (si no, IRF9540) — y compra 1 de repuesto
- [ ] **Diodo Schottky 1N5822** ×2 — uno principal, uno de respuesto
- [ ] **Inductor 220 µH, ≥3 A** ×1 (alternativas aceptables: 330 µH ≥2.5A, o 150 µH ≥3.5A)
- [ ] **Capacitor electrolítico salida**: 47 µF / 25 V low-ESR ×1
- [ ] **Capacitor cerámico salida**: 1 µF / 50 V X7R ×1
- [ ] **Capacitor electrolítico entrada**: 47 µF / 25 V ×1
- [ ] **Capacitor cerámico entrada**: 100 nF / 50 V ×2
- [ ] **Fusible 2A o 3A fast-blow + portafusibles** ×3 (con porta)
- [ ] **Disipador térmico TO-220 + pasta térmica + tornillo M3** ×1 (para el MOSFET)

**Divisor y medición**:
- [ ] **Resistor 22 kΩ 1/4 W 1 %** ×2 (uno para divisor de Vo, otro de repuesto/divisor 12V→ADC)
- [ ] **Resistor 10 kΩ 1/4 W 1 %** ×2
- [ ] **Capacitor cerámico 100 nF X7R** ×5 (para divisor, desacoples)

**Gate driver y aislamiento**:
- [ ] **Optoacoplador 6N137** ×1 (+ socket DIP-8 ×1)
- [ ] **Resistor 47 Ω 1/4 W** ×2 (gate)
- [ ] **Resistor 10 kΩ** ×2 (pull-up gate, pull-up Vd→gate)
- [ ] **Resistor 2.2 kΩ** ×2 (pull-up 6N137)
- [ ] **Resistor 1 kΩ** ×2 (base 2N2222)
- [ ] **Transistor 2N2222 (TO-92)** ×2

**Reguladores fijos**:
- [ ] **7805 TO-220** ×1 (+ disipador chico)
- [ ] **AMS1117-3.3 SOT-223** ×1 (en Paruro suele venir en módulo, también sirve)
- [ ] **Capacitor 100 nF** + **10 µF/25V** en entrada y salida de cada regulador (4 caps por regulador). Total: 8 caps adicionales si no usas los que ya tienes.

**Control y UI**:
- [ ] **Arduino UNO o Nano** ×1 (probablemente ya lo tienes)
- [ ] **Potenciómetro 10 kΩ lineal** ×1
- [ ] **OLED 0.96" I²C SSD1306** ×1
- [ ] **Módulo Bluetooth HC-05** ×1 (opcional según prioridades)
- [ ] **LED verde 5mm + LED amarillo 5mm** ×1 c/u
- [ ] **Resistor 330 Ω 1/4 W** ×2 (para LEDs)
- [ ] **(Evaluar) ACS712-5A** — sensor de corriente Hall, útil para limitación de corriente por software

**Hardware**:
- [ ] **Protoboard** ×1 (si no tienes uno bueno)
- [ ] **Jumpers macho-macho y macho-hembra** (set)
- [ ] **Borneras de 2 terminales atornillables** ×4 (entrada 12V + 3 salidas)
- [ ] **Conector jack DC 5.5×2.1mm hembra** ×1 (para entrada 12V)
- [ ] **Cable rojo y negro AWG18** (1 m de cada uno)

> **Presupuesto realista en Paruro (2026)**: si todo lo anterior se compra de calidad media, **S/. 70-110** (≈$20-30 USD). El inductor, el MOSFET y el OLED son los más caros. El resto es centavos.

---

## 9. Lo que viene después de la compra (resumen para no perder el hilo)

1. **Verificar PWM del Arduino**: subir frecuencia de Timer1 a 31.25 kHz vía `TCCR1B` (te paso el código cuando lleguemos a esa fase).
2. **Probar el gate drive** con el MOSFET sin carga (solo el LED amarillo simulando carga) para validar que el PWM llega limpio al gate.
3. **Armar el filtro LC + diodo**, medir con osciloscopio el rizado de Vo a distintas D.
4. **Cerrar el lazo**: ADC mide Vo, código PI calcula corrección, salida vuelve al PWM.
5. **Interfaz**: OLED muestra Vref / Vo medido, potenciómetro fija Vref, Bluetooth opcional.
6. **Protecciones**: pull-up del gate, fusible, supervisión de corriente con ACS712.

---

## 10. Lecturas anexas (cuando tengas tiempo, en orden de utilidad)

1. **TI SLVA477B** — *Basic Calculation of a Buck Converter's Power Stage*. Es **literalmente** un cookbook para tu proyecto. Ya lo tienes descargado. **Léelo entero** — son 8 páginas, te tomará 30 min. Lee primero §1-§7, después el Apéndice A (formulario).
2. **Mohan §7-3 a §7-3-3** (las páginas que está usando tu compañero). Si tienes el PDF de Mohan, son ≈10 páginas. Es la base teórica de TODO lo anterior.
3. **Analog Devices** — *Selecting the Right Inductor Current Ripple* — un artículo de 2 páginas, explica el 30 % como regla de oro y por qué.
4. **Erickson §2.1 a §2.4** — si quieres rigor académico: deriva volt-second balance y charge balance formalmente. Más denso pero el mejor texto que existe sobre este tema.
5. **Microchip AN3725** — para la parte de control (PI/PID en microcontrolador). Lo veremos después.

> **Cómo leer cada texto**: "Lee la sección X de [Y] y entiéndela como [la generalización de lo que vimos aquí, con la diferencia de que…]". Si en cualquier momento algo no cuadra con lo que pusimos arriba, **no sigas** — vuelve aquí o pregúntame.

---

## Apéndice — Verificación numérica de los cálculos de tu compañero

| Cálculo | Fórmula | Resultado teórico | Lo que escribió | OK |
|---|---|---|---|---|
| L mínimo (worst case) | L = Vd·Ts/(4·ΔIL) | 160 µH | 160 µH | ✅ |
| ΔIL con L=180 µH | ΔIL = Vd·Ts/(4L) | 0.533 A (26.7 %) | 0.53 / 26.5 % | ✅ |
| ΔIL con L=220 µH | ΔIL = Vd·Ts/(4L) | 0.436 A (21.8 %) | 0.436 / 21.8 % | ✅ |
| C mínimo @ L=220 µH, 5 % rizado, D=0.5 | C = (1-D)/(8·L·fs²·ΔVo/Vo) | 5.818 µF | 5.8182 µF | ✅ |
| ILB @ L=220 µH, D=0.5 | ILB = D(1-D)·Vd·Ts/(2L) | 218.2 mA | 218.18 mA | ✅ |
| Rmax para CCM | Rmax = Vo/ILB | 27.5 Ω | 27.3 Ω | ✅ |

**Conclusión**: los cálculos del compañero son matemáticamente correctos. Pasaron mi verificación independiente. **Puedes confiar en ellos**.
