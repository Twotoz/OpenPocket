#ifndef OPENPOCKET_AMT630A_H
#define OPENPOCKET_AMT630A_H

#include <stdint.h>

#define OPENPOCKET_FW_MAJOR 1u
#define OPENPOCKET_FW_MINOR 0u

typedef struct {
  uint16_t address;
  uint8_t value;
} register_write_t;

extern const __code register_write_t openpocket_registers[];
extern const __code uint16_t openpocket_register_count;

void register_write(uint16_t address, uint8_t value);
uint8_t register_read(uint16_t address);
void delay_cycles(uint16_t cycles);
void status_i2c_initialize(void);
void status_update(uint8_t video_flags, uint8_t standard);

#endif
