/*
 * oled.h
 *
 * Created: 15/05/2026 23:10:37
 *  Author: siule
 */ 

#ifndef OLED_H_
#define OLED_H_

#include <stdint.h>

void oled_init(void);
void oled_clear(void);
void oled_goto(uint8_t col, uint8_t page);  /* col: 0-127, page: 0-7 */
void oled_char(char c);
void oled_str(const char *s);

#endif