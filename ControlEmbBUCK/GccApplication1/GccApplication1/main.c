/*
 * blink_PD7_test.c
 *
 * Programa de prueba: LED intermitente en PD7 cada 1 segundo
 * Microcontrolador : ATmega328P (chip nuevo, fuses de fabrica)
 * Compilador       : XC8 (MPLAB X)
 * Reloj real       : 1 MHz  (8 MHz interno con CKDIV8 habilitado por defecto)
 *
 * Conexion hardware:
 *   PD7 (pin 13 del DIP28) --> resistencia 330 ohm --> LED --> GND
 *
 * IMPORTANTE sobre los fuses de fabrica del ATmega328P:
 *   CKSEL  = 0010  -> Oscilador RC interno 8 MHz
 *   CKDIV8 = 0     -> PROGRAMADO (activo bajo) -> divide por 8
 *   => Frecuencia efectiva = 8 MHz / 8 = 1 MHz
 *   Si F_CPU no coincide con el reloj real, los delays seran incorrectos.
 */

/* ---------------------------------------------------------------
 * F_CPU: le dice al compilador la frecuencia real del CPU.
 * __delay_ms() usa esta constante para calcular cuantos ciclos
 * de NOP necesita para generar el retardo pedido.
 * Con chip nuevo de fabrica = 1 000 000 Hz.
 * --------------------------------------------------------------- */
#define F_CPU 1000000UL

#include <xc.h>          /* Cabecera principal de XC8 para AVR.
                          * Incluye automaticamente el archivo de
                          * registros del device seleccionado en MPLAB X
                          * (iom328p.h), que define DDRD, PORTD, etc.  */

#include <util/delay.h>  /* Provee __delay_ms() y __delay_us().
                          * Calcula los ciclos de retardo en tiempo de
                          * compilacion usando F_CPU, por eso es CRITICO
                          * que F_CPU este definido ANTES de este include. */

/* ---------------------------------------------------------------
 * Macros de conveniencia para manipular bits (opcional pero claro)
 * SET_BIT  : pone el bit n en 1 sin tocar los demas
 * CLR_BIT  : pone el bit n en 0 sin tocar los demas
 * --------------------------------------------------------------- */
#define SET_BIT(reg, n)  ((reg) |=  (1U << (n)))
#define CLR_BIT(reg, n)  ((reg) &= ~(1U << (n)))

int main(void)
{
    /* ----------------------------------------------------------
     * PASO 1: Configurar PD7 como salida.
     *
     * DDRD (Data Direction Register D) controla la direccion de
     * los pines del puerto D. Cada bit corresponde a un pin:
     *   bit = 1 -> pin configurado como SALIDA
     *   bit = 0 -> pin configurado como ENTRADA (valor por defecto)
     *
     * (1 << 7) genera la mascara 0b10000000.
     * El operador |= asegura que solo se modifica el bit 7,
     * dejando los bits 0-6 intactos (importante si otros pines
     * ya tienen configuracion previa).
     * ---------------------------------------------------------- */
    SET_BIT(DDRD, 7);   /* PD7 = salida */

    /* ----------------------------------------------------------
     * PASO 2: Bucle infinito de parpadeo.
     * ---------------------------------------------------------- */
    while (1)
    {
        /* Encender LED: poner PD7 en alto (3.3V / 5V segun VCC) */
        SET_BIT(PORTD, 7);
        __delay_ms(1000);   /* Esperar 1000 ms = 1 s              */

        /* Apagar LED: poner PD7 en bajo (0V) */
        CLR_BIT(PORTD, 7);
        __delay_ms(1000);   /* Esperar 1000 ms = 1 s              */
    }

    return 0; /* Nunca se alcanza, pero buena practica en C */
}