#define F_CPU 16000000UL

#include <avr/io.h>
#include <util/delay.h>
#include "oled.h"

/* ---- PWM Timer1 Phase-Correct 31.25kHz (TOP=128) ---- */
void pwm_init(void)
{
	DDRB   |= (1 << PB1);
	ICR1    = 128;
	OCR1A   = 0;
	TCCR1A  = (1 << COM1A1) | (1 << WGM11);
	TCCR1B  = (1 << WGM13)  | (1 << CS10);
}

void pwm_set(uint8_t duty)
{
	if(duty > 128) duty = 128;
	OCR1A = duty;
}

/* ---- UART 9600 8N1 @ 16MHz (U2X=1, UBRR=207) ---- */
void uart_init(void)
{
	UCSR0A = (1 << U2X0);
	UBRR0  = 207;
	UCSR0B = (1 << TXEN0);
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

void uart_str(const char *s)
{
	while(*s)
	{
		while(!(UCSR0A & (1 << UDRE0)));
		UDR0 = *s++;
	}
}

static void u8_to_str(uint8_t val, char *buf)
{
	if(val == 0) { buf[0]='0'; buf[1]='\0'; return; }
	char tmp[4];
	uint8_t i = 0;
	while(val > 0) { tmp[i++] = '0' + (val % 10); val /= 10; }
	uint8_t j = 0;
	while(i > 0) buf[j++] = tmp[--i];
	buf[j] = '\0';
}

int main(void)
{
	pwm_init();
	uart_init();
	oled_init();
	oled_clear();

	oled_goto(0, 0);
	oled_str("BUCK - TEST");
	oled_goto(0, 3);
	oled_str("Duty:");

	uint8_t duty  = 0;
	int8_t  dir   = 1;
	uint8_t ticks = 0;

	while(1)
	{
		pwm_set(duty);

		/* Cada 25 ticks x 20ms = 500ms: actualiza OLED y BT */
		if(++ticks >= 25)
		{
			ticks = 0;

			uint8_t pct = (uint16_t)duty * 100 / 128;
			char buf[5];
			u8_to_str(pct, buf);
			uint8_t len = 0;
			while(buf[len]) len++;
			while(len < 3) { buf[len++] = ' '; buf[len] = '\0'; }

			oled_goto(36, 3);
			oled_str(buf);
			oled_goto(54, 3);
			oled_str("%  ");

			uart_str("D:");
			uart_str(buf);
			uart_str("%\r\n");
		}

		_delay_ms(20);

		duty += dir;
		if(duty == 128) dir = -1;
		if(duty == 0)   dir =  1;
	}
}