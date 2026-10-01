;; ============================================================
;; audio.s - So del gameplay (PSG AY-3-8912 directe)
;; Desperta Ferro
;; ============================================================
;; - SFX: taules de passos (període, volum, durada, mode) que
;;   sonen a qualsevol canal lliure; si tots estan ocupats es
;;   talla el mes antic.
;; - Fanfarria: jingle de 3 veus quan la sala queda neta (joc
;;   aturat, els 3 canals lliures).
;; - audio_update() avanca el so cada frame des del main loop.
;; - EL CODI I LES TAULES VIVEN A LA ZONA BAIXA (0x0100-0x3FFF),
;;   que mai desapareix amb el bank switching (Bank 5 a 0x4000).
;;   Per aixo el modul es .s (enllaca abans que els .c).
;; - El teclat (cpct_scanKeyboard_f) tambe usa el PSG (reg. 14)
;;   pero en moments diferents: no hi ha conflicte.
;; ============================================================
;; Format pas SFX (4 bytes): period, vol, dur, mode
;;   period = periode de to (lo) o de soroll (reg. 6) si NOISE
;;   vol    = 0-15
;;   dur    = frames (1/50 s); 0 = fi de l'efecte
;;   mode   = 0 = to, 1 = soroll
;; ============================================================

    .area   _CODE

;; ============================================================
;; Taules dels efectes
;; ============================================================

;; Espasa/thrust: fshhhh — ràfega de soroll descendent, sense to
;; (heroi i soldats). Sec i tallant.
s_swing:
    .db 24, 13, 2, 1
    .db 16, 12, 2, 1
    .db 10, 11, 2, 1
    .db 6, 9, 2, 1
    .db 0, 0, 0, 0

;; Projectil (fletxa/pedra): fshhh suau, sense to
s_whoosh:
    .db 28, 9, 2, 1
    .db 18, 8, 2, 1
    .db 12, 7, 2, 1
    .db 7, 6, 2, 1
    .db 0, 0, 0, 0

;; Cop a un enemic: rafega de soroll curta
s_impact:
    .db 8, 13, 2, 1
    .db 5, 12, 2, 1
    .db 3, 10, 2, 1
    .db 2, 8,  3, 1
    .db 0, 0, 0, 0

;; Mort d'enemic: soroll llarg que cau + cop greu final
;; (distint de l'impacte: mes llarg i amb cua de to greu)
s_death:
    .db 12, 15, 3, 1
    .db 8, 14, 3, 1
    .db 5, 12, 4, 1
    .db 3, 10, 4, 1
    .db 2, 7, 5, 1
    .db 255, 6, 4, 0
    .db 200, 5, 6, 0
    .db 0, 0, 0, 0

;; Porta: cruixit de fusta (tancar i obrir)
s_door:
    .db 20, 9, 4, 1
    .db 14, 10, 4, 1
    .db 9, 10, 4, 1
    .db 6, 9, 4, 1
    .db 3, 7, 5, 1
    .db 0, 0, 0, 0

;; Energia (bruixa/dimoni): zap magic rapid i fosc
s_energy:
    .db 15, 12, 1, 1
    .db 30, 10, 1, 1
    .db 50, 7, 1, 0
    .db 0, 0, 0, 0

;; Mos/atac cos-a-cos sense arma (gossos, senglar...): grinyol
s_bite:
    .db 10, 12, 2, 1
    .db 6, 11, 2, 1
    .db 4, 9, 2, 1
    .db 2, 7, 3, 1
    .db 0, 0, 0, 0

;; Xisclet agut de rata: chirp curt
s_squeak:
    .db 38, 12, 1, 0
    .db 30, 12, 1, 0
    .db 24, 12, 1, 0
    .db 18, 11, 2, 0
    .db 30, 9, 2, 0
    .db 0, 0, 0, 0

;; Moneda (piticlin): dos tons aguts ascendents i nets (estil classic coin)
s_coin:
    .db 55, 15, 2, 0    ;; 1r to agut fort (B5, vol 15, punch)
    .db 37, 15, 3, 0    ;; 2n to molt agut brillant (E6, vol 15)
    .db 37, 9,  2, 0    ;; decaiment rapid
    .db 37, 3,  1, 0    ;; tall final
    .db 0,  0,  0, 0

;; Taula d'efectes (ordre = SFX_* de audio.h)
s_sfx_tables:
    .dw s_swing
    .dw s_whoosh
    .dw s_impact
    .dw s_death
    .dw s_door
    .dw s_energy
    .dw s_bite
    .dw s_squeak
    .dw s_coin

;; ============================================================
;; Fanfarria (sala neta): jingle de 3 veus.
;; Format pas (4 bytes): dur, pa, pb, pc
;;   pa/pb/pc = periode de to dels canals A/B/C; 0 = silenci.
;;   dur = frames; 0 = final.
;; ============================================================
s_fanfare:
    .db 6, 214, 0, 214    ;; C5  .  C5
    .db 6, 170, 0, 0      ;; E5
    .db 6, 143, 0, 143    ;; G5  .  G5
    .db 6, 107, 170, 0    ;; C6  E5
    .db 6, 143, 0, 214    ;; G5  .  C5
    .db 6, 170, 0, 0      ;; E5
    .db 6, 214, 214, 0    ;; C5  C5
    .db 16, 214, 170, 143 ;; C5  E5  G5 (acord final)
    .db 0, 0, 0, 0

;; ============================================================
;; Estat del modul (_DATA, RAM fixa 0x8000+, mai bankejada)
;; ============================================================
    .area   _DATA

_s_chan_cur0: .dw 0
_s_chan_cnt0: .db 0
_s_chan_age0: .db 0
_s_chan_cur1: .dw 0
_s_chan_cnt1: .db 0
_s_chan_age1: .db 0
_s_chan_cur2: .dw 0
_s_chan_cnt2: .db 0
_s_chan_age2: .db 0
_s_tick:      .db 0
_s_mixer:     .db 0
_s_noise:     .db 0
_s_fan_cur:   .dw 0
_s_fan_cnt:   .db 0
_s_psg_reg:   .db 0
_s_psg_val:   .db 0

;; ============================================================
;; psg_reg(A = registre, E = valor) -> psg_write
;; Escriu un registre del PSG (patro del reproductor Arkos):
;; port A = registre/valor, port C = control 0xC0/0x80.
;; Trasheja A, B, C, D, E (no toca HL).
;; ============================================================
    .area   _CODE

psg_reg:
    ld   (_s_psg_reg), a
    ld   a, e
    ld   (_s_psg_val), a
    jp   psg_write

psg_write:
    ld   a, (_s_psg_reg)
    ld   e, a                ;; E = registre
    ld   a, (_s_psg_val)
    ld   d, a                ;; D = valor
    ;; NOTA: cal BC sencer (C=0x00). Amb nomes B, C quedava residual
    ;; (canal) i les escriptures anaven a registres PPI equivocats
    ;; (teclat mort / so trencat).
    ld   bc, #0xF400
    out  (c), e              ;; PPI port A = registre
    ld   bc, #0xF600
    ld   a, #0xC0
    out  (c), a              ;; Latch
    xor  a
    out  (c), a              ;; Inactive
    ld   bc, #0xF400
    out  (c), d              ;; PPI port A = valor
    ld   bc, #0xF600
    ld   a, #0x80
    out  (c), a              ;; Write
    xor  a
    out  (c), a              ;; Inactive
    ret

;; ============================================================
;; update_mixer: recalcula el registre 7 (mixer) a partir dels
;; modes dels canals actius.
;; Bits 0-2: to OFF per A/B/C; bits 3-5: soroll OFF per A/B/C.
;; ============================================================
update_mixer:
    ld   c, #0x38            ;; m = 0x38 (soroll OFF per tots)
    ;; --- canal 0 ---
    ld   hl, (_s_chan_cur0)
    ld   a, h
    or   l
    jr   z, um_c1
    inc  hl
    inc  hl
    inc  hl
    ld   a, (hl)             ;; mode
    bit  0, a
    ld   a, c
    jr   nz, um_c0_noise
    and  #0xFE
    jr   um_c0_done
um_c0_noise:
    and  #0xF7
    or   #0x01
um_c0_done:
    ld   c, a
    ;; --- canal 1 ---
um_c1:
    ld   hl, (_s_chan_cur1)
    ld   a, h
    or   l
    jr   z, um_c2
    inc  hl
    inc  hl
    inc  hl
    ld   a, (hl)
    bit  0, a
    ld   a, c
    jr   nz, um_c1_noise
    and  #0xFD
    jr   um_c1_done
um_c1_noise:
    and  #0xEF
    or   #0x02
um_c1_done:
    ld   c, a
    ;; --- canal 2 ---
um_c2:
    ld   hl, (_s_chan_cur2)
    ld   a, h
    or   l
    jr   z, um_done
    inc  hl
    inc  hl
    inc  hl
    ld   a, (hl)
    bit  0, a
    ld   a, c
    jr   nz, um_c2_noise
    and  #0xFB
    jr   um_c2_done
um_c2_noise:
    and  #0xDF
    or   #0x04
um_c2_done:
    ld   c, a
um_done:
    ld   a, (_s_mixer)
    cp   c
    ret  z
    ld   a, c
    ld   (_s_mixer), a
    ld   e, a
    ld   a, #7
    jp   psg_reg

;; ============================================================
;; apply_step(A = canal 0-2, HL = pas): escriu regs de to, volum
;; i (si soroll) periode de soroll del pas al canal.
;; ============================================================
apply_step:
    ld   c, a                ;; C = canal
    ld   a, (hl)             ;; period
    ld   e, a
    inc  hl
    ld   a, (hl)             ;; vol
    ld   d, a
    push de                  ;; desa period (E) + vol (D)
    ld   a, c
    add  a, a
    call psg_reg             ;; reg 2i = period
    ld   a, c
    add  a, a
    inc  a
    ld   e, #0
    call psg_reg             ;; reg 2i+1 = 0
    pop  de                  ;; E = period, D = vol
    push de                  ;; re-desa (period per al soroll)
    ld   a, c
    add  a, #8
    ld   e, d
    call psg_reg             ;; reg 8+i = vol
    pop  de                  ;; E = period
    inc  hl
    inc  hl                  ;; HL = pas+3 (mode)
    bit  0, (hl)
    ret  z
    ld   a, (_s_noise)
    cp   e
    ret  z                   ;; periode ja posat
    ld   a, e
    ld   (_s_noise), a
    ld   a, #6
    call psg_reg             ;; reg 6 = period de soroll
    ret

;; ============================================================
;; void audio_init(void)
;; PSG en silenci + estat net.
;; ============================================================
_audio_init::
    ld   hl, #0
    ld   (_s_chan_cur0), hl
    ld   (_s_chan_cur1), hl
    ld   (_s_chan_cur2), hl
    ld   (_s_fan_cur), hl
    xor  a
    ld   (_s_tick), a
    ld   (_s_noise), a
    ld   a, #0x38
    ld   (_s_mixer), a
    ld   a, #6
    ld   e, #0
    call psg_reg             ;; periode de soroll = 0
    ld   a, #7
    ld   e, #0x38
    call psg_reg             ;; mixer: tot OFF
    ld   a, #8
    ld   e, #0
    call psg_reg
    ld   a, #9
    ld   e, #0
    call psg_reg
    ld   a, #10
    ld   e, #0
    call psg_reg
    ret

;; ============================================================
;; void sfx_play(u8 sfx_id)   ;; arg u8 en registre A (__sdcccall 1)
;; ============================================================
_sfx_play::
    cp   #9
    ret  nc                  ;; id invalid
    ld   b, a                ;; B = id
    ld   hl, (_s_fan_cur)
    ld   a, h
    or   l
    ret  nz                  ;; fanfarria activa: ignora SFX
    ;; taula de l'efecte: s_sfx_tables + id*2
    ld   a, b
    add  a, a
    ld   c, a
    ld   b, #0
    ld   hl, #s_sfx_tables
    add  hl, bc
    ld   e, (hl)
    inc  hl
    ld   d, (hl)             ;; DE = taula de l'efecte
    push de                  ;; desa taula
    ;; cercar canal lliure (ordre 0, 1, 2)
    ld   hl, #_s_chan_cur0
    ld   c, #0               ;; C = canal
sp_chk0:
    ld   a, (hl)
    inc  hl
    or   (hl)
    jr   z, sp_found
    inc  hl
    inc  hl
    inc  hl                  ;; &cur del seguent canal
    inc  c
    ld   a, c
    cp   #3
    jr   nz, sp_chk0
    ;; tots ocupats: substituir el mes antic (menor age)
    ld   hl, #_s_chan_cur0
    inc  hl
    inc  hl
    inc  hl                  ;; &age0
    ld   c, #0               ;; mes antic = canal 0
    ld   d, #1               ;; index actual
    ld   a, (hl)
    ld   e, a                ;; E = age minima
sp_age_loop:
    inc  hl
    inc  hl
    inc  hl
    inc  hl                  ;; &age seguent
    ld   a, (hl)
    cp   e
    jr   nc, sp_age_next
    ld   e, a
    ld   c, d
sp_age_next:
    inc  d
    ld   a, d
    cp   #3
    jr   nz, sp_age_loop
sp_found:                    ;; C = canal
    ld   a, c
    add  a, a
    add  a, a
    ld   e, a
    ld   d, #0
    ld   hl, #_s_chan_cur0
    add  hl, de              ;; HL = &cur del canal
    pop  de                  ;; DE = taula
    push de                  ;; re-desa per a apply_step
    ld   (hl), e
    inc  hl
    ld   (hl), d             ;; cur = taula
    inc  hl                  ;; &cnt
    push hl                  ;; desa &cnt
    ex   de, hl              ;; HL = taula
    inc  hl
    inc  hl                  ;; HL = taula+2 (dur 1r pas)
    ld   a, (hl)
    pop  hl                  ;; &cnt
    ld   (hl), a             ;; cnt = dur
    inc  hl                  ;; &age
    ld   a, (_s_tick)
    ld   (hl), a             ;; age = tick
    pop  hl                  ;; HL = taula
    ld   a, c                ;; A = canal
    call apply_step
    jp   update_mixer

;; ============================================================
;; void audio_update(void)
;; Avanca el so un frame (fanfarria o SFX) i reescriu el mixer.
;; ============================================================
_audio_update::
    ld   hl, #_s_tick
    inc  (hl)
    ;; fanfarria activa?
    ld   hl, (_s_fan_cur)
    ld   a, h
    or   l
    jp   nz, au_fanfare
    ;; --- SFX: per cada canal ---
    ld   b, #0               ;; B = canal
au_chan_loop:
    push bc                  ;; desa canal
    ld   hl, #_s_chan_cur0
    ld   a, b
    add  a, a
    add  a, a
    ld   c, a
    ld   b, #0
    add  hl, bc              ;; HL = &cur del canal
    ld   e, (hl)
    inc  hl
    ld   d, (hl)             ;; DE = cur (pas actual)
    inc  hl                  ;; &cnt
    ld   a, d
    or   e
    jr   z, au_next          ;; canal lliure
    ld   a, (hl)
    or   a
    jr   z, au_step_done     ;; cnt == 0: avançar
    dec  (hl)
    jr   au_next
au_step_done:
    ;; DE = pas actual, HL = &cnt
    ex   de, hl              ;; HL = pas, DE = &cnt
    inc  hl
    inc  hl
    inc  hl
    inc  hl                  ;; HL = pas seguent (pas+4)
    push hl                  ;; desa pas seguent
    inc  hl
    inc  hl                  ;; HL = pas+6 (dur del seguent)
    ld   a, (hl)
    or   a
    jr   z, au_chan_end      ;; fi d'efecte
    pop  hl                  ;; HL = pas seguent
    ex   de, hl              ;; HL = &cnt, DE = pas seguent
    push de                  ;; desa pas seguent
    dec  hl
    dec  hl                  ;; &cur
    ld   (hl), e
    inc  hl
    ld   (hl), d             ;; cur = pas seguent
    inc  hl                  ;; &cnt
    ex   de, hl              ;; HL = pas seguent, DE = &cnt
    inc  hl
    inc  hl                  ;; HL = pas+6 (dur)
    ld   a, (hl)
    ex   de, hl              ;; HL = &cnt
    ld   (hl), a             ;; cnt = dur del seguent
    pop  hl                  ;; HL = pas seguent
    pop  bc                  ;; B = canal
    ld   a, b
    push bc                  ;; torna a desar canal
    call apply_step          ;; A = canal, HL = pas
    jr   au_next
au_chan_end:
    ;; entra amb: HL = pas+6 (dur = 0), stack = [pas_seg, canal]
    pop  hl                  ;; descarta el punter
    ex   de, hl              ;; HL = &cnt
    dec  hl
    dec  hl                  ;; &cur
    xor  a
    ld   (hl), a
    inc  hl
    ld   (hl), a             ;; cur = 0
    inc  hl
    ld   (hl), a             ;; cnt = 0
    pop  bc                  ;; B = canal
    ld   a, b
    add  a, #8
    ld   e, #0
    call psg_reg             ;; vol = 0
    inc  b
    ld   a, b
    cp   #3
    jr   nz, au_chan_loop
    jp   update_mixer
au_next:
    pop  bc                  ;; B = canal
    inc  b
    ld   a, b
    cp   #3
    jr   nz, au_chan_loop
    jp   update_mixer

;; ============================================================
;; Fanfarria: avanca el patro de 3 veus
;; ============================================================
au_fanfare:
    ld   hl, #_s_fan_cnt
    ld   a, (hl)
    or   a
    jr   z, au_fan_step
    dec  (hl)
    ret
au_fan_step:
    ld   hl, (_s_fan_cur)    ;; HL = pas de fanfarria
    ld   a, (hl)             ;; dur
    ld   b, a                ;; B = dur
    inc  hl
    ld   e, (hl)             ;; pa
    ld   a, #0
    call psg_reg             ;; reg 0 = pa
    ld   a, #1
    ld   e, #0
    call psg_reg             ;; reg 1 = 0
    ld   hl, (_s_fan_cur)
    inc  hl
    inc  hl
    ld   e, (hl)             ;; pb
    ld   a, #2
    call psg_reg             ;; reg 2 = pb
    ld   a, #3
    ld   e, #0
    call psg_reg             ;; reg 3 = 0
    ld   hl, (_s_fan_cur)
    inc  hl
    inc  hl
    inc  hl
    ld   e, (hl)             ;; pc
    ld   a, #4
    call psg_reg             ;; reg 4 = pc
    ld   a, #5
    ld   e, #0
    call psg_reg             ;; reg 5 = 0
    ;; volums (11/8/9 si la nota sona, 0 si silenci)
    ld   hl, (_s_fan_cur)
    inc  hl
    ld   a, (hl)             ;; pa
    or   a
    jr   z, af_va0
    ld   e, #11
    jr   af_va1
af_va0:
    ld   e, #0
af_va1:
    ld   a, #8
    call psg_reg             ;; vol A
    ld   hl, (_s_fan_cur)
    inc  hl
    inc  hl
    ld   a, (hl)             ;; pb
    or   a
    jr   z, af_vb0
    ld   e, #8
    jr   af_vb1
af_vb0:
    ld   e, #0
af_vb1:
    ld   a, #9
    call psg_reg             ;; vol B
    ld   hl, (_s_fan_cur)
    inc  hl
    inc  hl
    inc  hl
    ld   a, (hl)             ;; pc
    or   a
    jr   z, af_vc0
    ld   e, #9
    jr   af_vc1
af_vc0:
    ld   e, #0
af_vc1:
    ld   a, #10
    call psg_reg             ;; vol C
    ;; cnt = dur; avançar o aturar
    ld   hl, (_s_fan_cur)
    ld   a, (hl)             ;; dur del pas actual
    ld   hl, #_s_fan_cnt
    ld   (hl), a
    or   a
    jr   z, af_end           ;; dur == 0: final
    ld   hl, (_s_fan_cur)
    inc  hl
    inc  hl
    inc  hl
    inc  hl
    ld   (_s_fan_cur), hl
    ret
af_end:
    ;; final de fanfarria: silenciar els 3 canals (l'acord final
    ;; no pot quedar sustentant)
    xor  a
    ld   hl, #_s_fan_cur
    ld   (hl), a
    inc  hl
    ld   (hl), a             ;; s_fan_cur = 0
    ld   a, #8
    ld   e, #0
    call psg_reg             ;; vol A = 0
    ld   a, #9
    ld   e, #0
    call psg_reg             ;; vol B = 0
    ld   a, #10
    ld   e, #0
    call psg_reg             ;; vol C = 0
    ret

;; ============================================================
;; void fanfare_play(void)
;; Atura els SFX i toca el jingle de 3 veus.
;; ============================================================
_fanfare_play::
    xor  a
    ld   hl, #_s_chan_cur0
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a
    inc  hl
    ld   (hl), a             ;; cur/cnt/age x3 = 12 B a 0
    ;; volums a 0
    ld   a, #8
    ld   e, #0
    call psg_reg
    ld   a, #9
    ld   e, #0
    call psg_reg
    ld   a, #10
    ld   e, #0
    call psg_reg
    ;; activar fanfarria
    ld   hl, #s_fanfare
    ld   (_s_fan_cur), hl
    xor  a
    ld   (_s_fan_cnt), a
    ;; mixer: to ON, soroll OFF
    ld   a, #0x38
    ld   (_s_mixer), a
    ld   e, a
    ld   a, #7
    jp   psg_reg
