#ifndef SCROLL_H
#define SCROLL_H

#include "cpctelera.h"

// Escriu R12/R13 del CRTC (implementat a engine/crtc.s).
// word_off en unitats de paraula (1 = 2 bytes = 1 caracter CRTC).
void crtc_set_scroll(u16 word_off);

// Escriu R3 del CRTC (amplada HSYNC). Per al scroll de 4 px: 0xF5/0xF6.
void crtc_set_r3(u8 val);

// Omple la pantalla (16 KB, format interleaved del CPC) amb el patro
// del mon per al desplacament 0.
void scroll_init(void);

// Scroll horitzontal continu: 1 subtile (8 px) cap a dir (>0 dreta).
void scroll_step_dir(i8 dir);

// Equivalent a scroll_step_dir(+1).
void scroll_step(void);

// Nombre de passos de scroll fets (1 pas = 8 px).
u16 scroll_get_offset(void);

// Restaura el fons (des del tilemap, posicio de scroll actual) en un
// rectangle de pantalla (sx/sy en bytes/linies, w bytes x h linies).
void screen_bg_rect(u16 sy, u16 sx, u8 w, u8 h);

// Dibuixa un sprite emmascarat format interleaved [mask,img] per byte.
// L'adreçament via disp_addr gestiona el wrap de MA automaticament.
void screen_blit_sprite(const u8* spr, u16 sy, u16 sx, u8 w, u8 h);

// Redibuixa el HUD (40 linies inferiors) a la posicio de scroll actual.
// Cal cridar-ho cada cop que la camera es mou (i un cop a l'inici).
void hud_draw(void);

// Finestra vertical del nivell real (subtile row que es mostra a dalt).
extern u16 g_cam_subrow;

// Desplaca la camera verticalment dir subtiles. Nomes mou la camera.
// Retorna 1 si s'ha mogut, 0 si estava al limit.
u8 scroll_step_v(i8 dir);

// Offset MA real (horitzontal + vertical) per a l'sprite / HUD.
u16 scroll_get_ma(void);

// Posicio de camera horitzontal en unitats de 4 px (per a l'sprite).
u16 scroll_get_hpos(void);

// Maxim de g_cam_subrow (LEVEL_SROWS - PLAY_ROWS).
#define CAM_SUBROW_MAX 124

// Solidesa pel CAP del nivell a (scol, srow) subtiles 8x8 (coords de NIVELL).
u8 level_solid(u16 scol, u16 srow);

// Offset de terra del pixel xpix (0..15) del tile. 0xFF = no solid.
u8 level_floor_yoff(u16 scol, u16 srow, u8 xpix);

// Sprite amb desat/restauracio del fons (sense cerques al mapa).
void screen_restore(void);
void screen_blit_saved(const u8* spr, u16 sy, u16 sx, u8 w, u8 h);

#endif // SCROLL_H
