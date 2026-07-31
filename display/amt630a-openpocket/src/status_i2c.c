#include "amt630a.h"

// P89CE558-compatible I2C peripheral used by the AMT630A MCU.
__sfr __at(0xd8) S1CON;
__sfr __at(0xd9) S1STA;
__sfr __at(0xda) S1DAT;
__sfr __at(0xdb) S1ADR;
__sbit __at(0xaf) EA;

static volatile __data uint8_t status_bytes[5];
static volatile __data uint8_t status_index;

void status_update(uint8_t video_flags, uint8_t standard)
{
  status_bytes[0] = 0xa5;
  status_bytes[1] = video_flags;
  status_bytes[2] = standard;
  status_bytes[3] = OPENPOCKET_FW_MAJOR;
  status_bytes[4] = OPENPOCKET_FW_MINOR;
}

void status_i2c_initialize(void)
{
  status_index = 0;
  S1ADR = 0xb0;  // 7-bit address 0x58, general-call disabled.
  S1CON = 0x44;  // ENS1 | AA; interrupt flag clear.
  EA = 1;
}

void i2c_interrupt(void) __interrupt(5)
{
  switch (S1STA) {
    case 0x60:  // SLA+W
      status_index = 0;
      break;
    case 0x80:  // register index
      status_index = S1DAT < sizeof(status_bytes) ? S1DAT : 0;
      break;
    case 0xa8:  // SLA+R
    case 0xb8:  // byte transmitted, ACK
      S1DAT = status_bytes[status_index];
      if (status_index + 1u < sizeof(status_bytes)) ++status_index;
      break;
    default:
      break;
  }
  S1CON = (S1CON & 0xf4u) | 0x44u;
}
