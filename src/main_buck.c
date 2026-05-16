#define F_CPU 16000000UL

#include <avr/io.h>
#include <util/delay.h>
#include <string.h>
#include "oled.h"

/* ================================================================
 * PWM - Timer1 Phase-Correct 31.25kHz, TOP=128, salida en PB1
 * ================================================================ */
void pwm_init(void)
{
	DDRB  |= (1 << PB1);
	ICR1   = 128;
	OCR1A  = 0;
	TCCR1A = (1 << COM1A1) | (1 << WGM11);
	TCCR1B = (1 << WGM13)  | (1 << CS10);
}

void pwm_set(uint8_t duty)
{
	if(duty > 128) duty = 128;
	OCR1A = duty;
}

/* ================================================================
 * UART - 9600 8N1 @ 16MHz, U2X=1, UBRR=207
 * TX: envio de telemetria al HC-05
 * RX: recepcion de comandos desde el celular/PC
 * ================================================================ */
void uart_init(void)
{
	UCSR0A = (1 << U2X0);
	UBRR0  = 207;
	UCSR0B = (1 << TXEN0) | (1 << RXEN0);  /* habilita TX y RX */
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

/* ================================================================
 * Buffer de recepcion UART
 * Lee bytes disponibles sin bloquear el loop principal.
 * Cuando llega '\n' devuelve 1 y deja el comando en rx_buf.
 * ================================================================ */
static char    rx_buf[32];
static uint8_t rx_idx = 0;

uint8_t uart_rx_line(void)
{
	/* RXC0=1 significa que hay un byte nuevo en UDR0 */
	while(UCSR0A & (1 << RXC0))
	{
		char c = UDR0;
		if(c == '\n' || c == '\r')
		{
			if(rx_idx > 0)
			{
				rx_buf[rx_idx] = '\0';
				rx_idx = 0;
				return 1;   /* linea completa lista en rx_buf */
			}
		}
		else if(rx_idx < 31)
		{
			rx_buf[rx_idx++] = c;
		}
	}
	return 0;
}

/* ================================================================
 * Conversion uint a string (sin printf)
 * ================================================================ */
static void u8_to_str(uint8_t val, char *buf)
{
	if(val == 0) { buf[0]='0'; buf[1]='\0'; return; }
	char tmp[4]; uint8_t i=0;
	while(val > 0) { tmp[i++] = '0' + (val % 10); val /= 10; }
	uint8_t j=0;
	while(i > 0) buf[j++] = tmp[--i];
	buf[j] = '\0';
}

/* Parsea "X.X" o "X" de una cadena y devuelve valor en decimas
 * Ej: "5.5" -> 55,  "9" -> 90,  "0.0" -> 0              */
static uint8_t parse_decimas(const char *s)
{
	uint8_t entero = 0, decimal = 0;
	while(*s >= '0' && *s <= '9') entero = entero*10 + (*s++ - '0');
	if(*s == '.')
	{
		s++;
		if(*s >= '0' && *s <= '9') decimal = *s - '0';
	}
	return entero * 10 + decimal;  /* ej: 5.5 -> 55 decimas */
}

/* ================================================================
 * Parseo de comandos
 * Protocolo: SET V X.X | GET V | GET I | GET STATUS | RESET
 * ================================================================ */
static uint8_t setpoint_decimas = 0;  /* voltaje objetivo en decimas: 55 = 5.5V */

static void oled_update_setpoint(void)
{
	char buf[8];
	u8_to_str(setpoint_decimas / 10, buf);
	oled_goto(30, 2);
	oled_str(buf); oled_char('.');
	u8_to_str(setpoint_decimas % 10, buf);
	oled_str(buf); oled_str(" V  ");

	uint8_t duty = (uint16_t)setpoint_decimas * 128 / 120;
	pwm_set(duty);
	uint8_t pct = (uint16_t)duty * 100 / 128;
	u8_to_str(pct, buf);
	oled_goto(36, 4);
	oled_str(buf); oled_str("%  ");
}

void parse_command(const char *cmd)
{
	if(strncmp(cmd, "SET V ", 6) == 0)
	{
		setpoint_decimas = parse_decimas(cmd + 6);
		if(setpoint_decimas > 90) setpoint_decimas = 90;
		oled_update_setpoint();   /* actualiza OLED al instante */
		uart_str("OK\r\n");
	}
	else if(strcmp(cmd, "GET V") == 0)
	{
		/* Por ahora devuelve el setpoint (sin ADC real aun) */
		char buf[8];
		u8_to_str(setpoint_decimas / 10, buf);
		uart_str("V ");
		uart_str(buf);
		uart_str(".");
		u8_to_str(setpoint_decimas % 10, buf);
		uart_str(buf);
		uart_str("\r\n");
	}
	else if(strcmp(cmd, "GET STATUS") == 0)
	{
		uart_str("STATUS OK\r\n");
	}
	else if(strcmp(cmd, "RESET") == 0)
	{
		setpoint_decimas = 0;
		uart_str("OK\r\n");
	}
	else
	{
		uart_str("ERR comando desconocido\r\n");
	}
}

/* ================================================================
 * OLED helpers
 * ================================================================ */
static void oled_str_pad(const char *s, uint8_t total)
{
	/* Imprime s y rellena con espacios hasta total caracteres
	 * para borrar residuos de valores anteriores mas largos */
	uint8_t len = 0;
	const char *p = s;
	while(*p++) len++;
	oled_str(s);
	while(len++ < total) oled_char(' ');
}

/* ================================================================
 * MAIN
 * ================================================================ */
int main(void)
{
	pwm_init();
	uart_init();
	oled_init();
	oled_clear();

	oled_goto(0, 0); oled_str("BUCK CTRL");
	oled_goto(0, 2); oled_str("Set:");
	oled_goto(0, 4); oled_str("Duty:");
	oled_goto(0, 6); oled_str("BT: OK");

	uint8_t ticks = 0;

	while(1)
	{
		/* --- Recepcion cada 1ms para no perder bytes a 9600 baud --- */
		for(uint8_t ms = 0; ms < 20; ms++)
		{
			if(uart_rx_line()) parse_command(rx_buf);
			_delay_ms(1);
		}

		/* --- Cada 500ms: actualiza display y envia telemetria --- */
		if(++ticks >= 25)
		{
			ticks = 0;

			/* Duty cycle proporcional al setpoint (open loop por ahora)
			 * D = Vset/Vin = setpoint_decimas/10 / 12
			 * OCR1A = D * 128 = setpoint_decimas * 128 / 120 */
			uint8_t duty = (uint16_t)setpoint_decimas * 128 / 120;
			pwm_set(duty);

			/* OLED: muestra setpoint como "X.X V" */
			char buf[8];
			u8_to_str(setpoint_decimas / 10, buf);
			oled_goto(30, 2);
			oled_str(buf); oled_char('.');
			u8_to_str(setpoint_decimas % 10, buf);
			oled_str_pad(buf, 1);
			oled_str(" V  ");

			/* OLED: muestra duty como porcentaje */
			uint8_t pct = (uint16_t)duty * 100 / 128;
			u8_to_str(pct, buf);
			oled_goto(36, 4);
			oled_str_pad(buf, 3);
			oled_str("%  ");

			/* BT: envia telemetria */
			uart_str("V ");
			u8_to_str(setpoint_decimas / 10, buf);
			uart_str(buf); uart_str(".");
			u8_to_str(setpoint_decimas % 10, buf);
			uart_str(buf); uart_str("\r\n");
		}

	}
}
