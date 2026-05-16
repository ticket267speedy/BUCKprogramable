#define F_CPU 8000000UL

#include <avr/io.h>
#include "oled.h"

int main(void)
{
    oled_init();
    oled_clear();

    oled_goto(0, 0);
    oled_str("OLED OK");

    oled_goto(0, 2);
    oled_str("Vout: 0.0 V");

    oled_goto(0, 4);
    oled_str("Iout: 0.0 A");

    while(1) {}
}
