#include "amt630a.h"

void register_write(uint16_t address, uint8_t value)
{
  *((volatile __xdata uint8_t*)address) = value;
}

uint8_t register_read(uint16_t address)
{
  return *((volatile __xdata uint8_t*)address);
}

void delay_cycles(uint16_t cycles)
{
  volatile uint16_t index;
  for (index = 0; index < cycles; ++index) {
    __asm nop __endasm;
  }
}

void main(void)
{
  uint16_t index;
  uint8_t stable = 0;
  uint8_t prior_standard = 0xff;

  // Power and PLL settling occurs with panel backlight held off externally.
  delay_cycles(60000);
  for (index = 0; index < openpocket_register_count; ++index) {
    register_write(openpocket_registers[index].address,
                   openpocket_registers[index].value);
  }
  status_i2c_initialize();
  status_update(0x03, 0);

  for (;;) {
    const uint8_t detect = register_read(0xfe2a);
    const uint8_t current_standard =
        (detect & 0x10u) == 0 ? 0u :
        ((register_read(0xfe28) & 0x04u) != 0 ? 2u : 1u);
    if (current_standard == prior_standard) {
      if (stable != 0xffu) ++stable;
    } else {
      stable = 0;
      prior_standard = current_standard;
    }
    if (current_standard == 0) {
      // Keep the TCON running; periodically request decoder resynchronization.
      register_write(0xfea0, 0x01);
      delay_cycles(256);
      register_write(0xfea0, 0x00);
      status_update(0x03, 0);
    } else if (stable >= 4) {
      status_update(0x07, current_standard);
    } else {
      status_update(0x03, 4);
    }
    delay_cycles(12000);
  }
}
