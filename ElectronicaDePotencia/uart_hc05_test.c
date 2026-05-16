#define F_CPU 1000000UL

#include <avr/io.h>
#include <util/delay.h>

void uart_init(void)
{
    /* U2X=1: modo doble velocidad. Con F_CPU=1MHz y UBRR=12
     * el baudrate real es 1000000/(8*13) = 9615 baud -> error 0.16%, ok.
     * Sin U2X el error seria 7%, demasiado para que HC-05 lo entienda. */
    UCSR0A = (1 << U2X0);
    UBRR0  = 12;
    UCSR0B = (1 << TXEN0);   /* solo habilita TX, RX no se necesita aun */
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);  /* 8N1 */
}

void uart_send(const char *s)
{
    while (*s)
    {
        while (!(UCSR0A & (1 << UDRE0)));  /* espera buffer libre */
        UDR0 = *s++;
    }
}

int main(void)
{
    uart_init();
    DDRD |= (1 << 7);

    while (1)
    {
        PORTD |=  (1 << 7);
        uart_send("ON\r\n");
        _delay_ms(1000);

        PORTD &= ~(1 << 7);
        uart_send("OFF\r\n");
        _delay_ms(1000);
    }
}
