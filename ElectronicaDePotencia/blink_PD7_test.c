#define F_CPU 1000000UL   // chip nuevo de fabrica: 8MHz / CKDIV8 = 1MHz

#include <avr/io.h>
#include <util/delay.h>

int main(void)
{
    DDRD |= (1 << 7);   // PD7 como salida

    while (1)
    {
        PORTD |=  (1 << 7);   // LED on
        _delay_ms(1000);
        PORTD &= ~(1 << 7);   // LED off
        _delay_ms(1000);
    }
}
