#ifndef CPCTELERA_H
#define CPCTELERA_H

// ============================================================
// cpctelera.h - Capa autònoma de maquinari Amstrad CPC
// Substitut natiu per a SDCC 4.5+ sense dependències de CPCtelera
// ============================================================

typedef unsigned char  u8;
typedef unsigned short u16;
typedef signed char    i8;
typedef signed short   i16;
typedef unsigned long  u32;
typedef signed long    i32;

#include <string.h>

// Funcions de vídeo i maquinari Gate Array
void cpct_disableFirmware(void);
void cpct_setVideoMode(u8 mode);
void cpct_setBorder(u8 hw_color);
void cpct_setPALColour(u8 pen, u8 hw_color);
void cpc_bank_set(u8 bank_val);
void cpc_bank_restore(void);

// Sincronisme VSYNC
void cpct_waitVSYNC(void);

// Teclat i Joystick (PSG AY-3-8912)
extern u8 cpct_keyboardStatusBuffer[10];
extern u8 cpct_mode_rom_status;
void cpct_scanKeyboard_f(void);
u8   cpct_isKeyPressed(i16 key_id);

// Memòria i blitter
#define cpct_memcpy(dst, src, size) memcpy((dst), (src), (size))
#define cpct_memset(dst, val, size) memset((dst), (val), (size))

// Enumeració canònica de tecles i joysticks CPC
typedef enum cpct_e_keyID {
  // Línia 00h
  Key_CursorUp     = (i16)0x0100,
  Key_CursorRight  = (i16)0x0200,
  Key_CursorDown   = (i16)0x0400,
  Key_F9           = (i16)0x0800,
  Key_F6           = (i16)0x1000,
  Key_F3           = (i16)0x2000,
  Key_Enter        = (i16)0x4000,
  Key_FDot         = (i16)0x8000,

  // Línia 01h
  Key_CursorLeft   = (i16)0x0101,
  Key_Copy         = (i16)0x0201,
  Key_F7           = (i16)0x0401,
  Key_F8           = (i16)0x0801,
  Key_F5           = (i16)0x1001,
  Key_F1           = (i16)0x2001,
  Key_F2           = (i16)0x4001,
  Key_F0           = (i16)0x8001,

  // Línia 02h
  Key_Clr          = (i16)0x0102,
  Key_OpenBracket  = (i16)0x0202,
  Key_Return       = (i16)0x0402,
  Key_CloseBracket = (i16)0x0802,
  Key_F4           = (i16)0x1002,
  Key_Shift        = (i16)0x2002,
  Key_BackSlash    = (i16)0x4002,
  Key_Control      = (i16)0x8002,

  // Línia 03h
  Key_Caret        = (i16)0x0103,
  Key_Hyphen       = (i16)0x0203,
  Key_At           = (i16)0x0403,
  Key_P            = (i16)0x0803,
  Key_SemiColon    = (i16)0x1003,
  Key_Colon        = (i16)0x2003,
  Key_Slash        = (i16)0x4003,
  Key_Dot          = (i16)0x8003,

  // Línia 04h
  Key_0            = (i16)0x0104,
  Key_9            = (i16)0x0204,
  Key_O            = (i16)0x0404,
  Key_I            = (i16)0x0804,
  Key_L            = (i16)0x1004,
  Key_K            = (i16)0x2004,
  Key_M            = (i16)0x4004,
  Key_Comma        = (i16)0x8004,

  // Línia 05h
  Key_8            = (i16)0x0105,
  Key_7            = (i16)0x0205,
  Key_U            = (i16)0x0405,
  Key_Y            = (i16)0x0805,
  Key_H            = (i16)0x1005,
  Key_J            = (i16)0x2005,
  Key_N            = (i16)0x4005,
  Key_Space        = (i16)0x8005,

  // Línia 06h
  Key_6            = (i16)0x0106,
  Joy1_Up          = (i16)0x0106,
  Key_5            = (i16)0x0206,
  Joy1_Down        = (i16)0x0206,
  Key_R            = (i16)0x0406,
  Joy1_Left        = (i16)0x0406,
  Key_T            = (i16)0x0806,
  Joy1_Right       = (i16)0x0806,
  Key_G            = (i16)0x1006,
  Joy1_Fire1       = (i16)0x1006,
  Key_F            = (i16)0x2006,
  Joy1_Fire2       = (i16)0x2006,
  Key_B            = (i16)0x4006,
  Joy1_Fire3       = (i16)0x4006,
  Key_V            = (i16)0x8006,

  // Línia 07h
  Key_4            = (i16)0x0107,
  Key_3            = (i16)0x0207,
  Key_E            = (i16)0x0407,
  Key_W            = (i16)0x0807,
  Key_S            = (i16)0x1007,
  Key_D            = (i16)0x2007,
  Key_C            = (i16)0x4007,
  Key_X            = (i16)0x8007,

  // Línia 08h
  Key_1            = (i16)0x0108,
  Key_2            = (i16)0x0208,
  Key_Esc          = (i16)0x0408,
  Key_Q            = (i16)0x0808,
  Key_Tab          = (i16)0x1008,
  Key_A            = (i16)0x2008,
  Key_CapsLock     = (i16)0x4008,
  Key_Z            = (i16)0x8008,

  // Línia 09h
  Joy0_Up          = (i16)0x0109,
  Joy0_Down        = (i16)0x0209,
  Joy0_Left        = (i16)0x0409,
  Joy0_Right       = (i16)0x0809,
  Joy0_Fire1       = (i16)0x1009,
  Joy0_Fire2       = (i16)0x2009,
  Joy0_Fire3       = (i16)0x4009,
  Key_Del          = (i16)0x8009
} cpct_keyID;

#endif // CPCTELERA_H
