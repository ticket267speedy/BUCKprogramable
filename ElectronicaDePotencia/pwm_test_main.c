#define F_CPU 8000000UL

#include <avr/io.h>
#include <util/delay.h>

/* ================================================================
 * Timer1 - Phase Correct PWM a 31.25 kHz
 *
 * Modo: Phase-Correct PWM con TOP = ICR1
 * El contador sube de 0 a ICR1, luego baja de ICR1 a 0 (simetrico).
 *
 * Formula: f_PWM = F_CPU / (2 * N * TOP)
 *   31250 = 8000000 / (2 * 1 * TOP)
 *   TOP   = 8000000 / (2 * 31250) = 128
 *
 * Resolucion: 128 pasos -> duty cycle de 0/128 a 128/128
 * OCR1A = 0   -> 0%  (siempre LOW)
 * OCR1A = 64  -> 50%
 * OCR1A = 128 -> 100% (siempre HIGH)
 *
 * Salida hardware: OC1A = PB1 (pin 15 del DIP28)
 * No se puede cambiar a otro pin sin perder el PWM por hardware.
 * ================================================================ */

void pwm_init(void)
{
    /* PB1 como salida (OC1A) */
    DDRB |= (1 << PB1);

    /* ICR1 = TOP = 128 */
    ICR1 = 128;

    /* OCR1A = valor inicial de duty cycle (50% para test) */
    OCR1A = 64;

    /* TCCR1A:
     *   COM1A1=1, COM1A0=0 -> non-inverting: OC1A se limpia subiendo,
     *                         se setea bajando (duty = OCR1A/ICR1)
     *   WGM11=1, WGM10=0   -> parte del modo Phase-Correct PWM con ICR1
     *
     * TCCR1B:
     *   WGM13=1, WGM12=0   -> completa el modo (WGM = 1010 = modo 10)
     *   CS10=1              -> prescaler = 1 (sin division, maximo freq) */
    TCCR1A = (1 << COM1A1) | (1 << WGM11);
    TCCR1B = (1 << WGM13)  | (1 << CS10);
}

/* duty: 0 a 128 (entero directo, no porcentaje)
 * Ejemplo: pwm_set(64) -> 50%, pwm_set(128) -> 100% */
void pwm_set(uint8_t duty)
{
    if(duty > 128) duty = 128;
    OCR1A = duty;
}

int main(void)
{
    pwm_init();

    /* Sube el duty de 0 a 100% y baja, en bucle.
     * Con LED en PB1 + resistor 330ohm a GND veras el brillo variar.
     * Con osciloscopio veras la senal a 31.25kHz variando el ancho. */
    while(1)
    {
        for(uint8_t d = 0; d <= 128; d++)
        {
            pwm_set(d);
            _delay_ms(10);
        }
        for(uint8_t d = 128; d > 0; d--)
        {
            pwm_set(d);
            _delay_ms(10);
        }
    }
}
