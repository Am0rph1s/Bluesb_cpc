.module assets_fdc

        .globl _assets_fdc_load_generic
        .globl _assets_bank_select
        .globl _assets_bank_restore
        .globl _g_fdc_ondisk_bytes
        .globl _g_fdc_sector_count
        .globl _g_fdc_chs_table
        .globl _g_fdc_dest_bank
        .globl _g_fdc_dest_addr
        .globl _g_fdc_home_bank
        .globl MUS_HOLD          ;; _g_mus_hold del GAME (obj/fdc_hold.s,
                                 ;; generat del mapa: patro front_ext)
        .globl GBANK_ADDR        ;; _g_bank del GAME (mateix EQU)

;; Mapa de RAM:
;;   FDC_BUF i FDC_WORK han d'estar en RAM base, no en zona bancable.
;;   FDC_BUF (sector 512B):   0xB800
;;   FDC_WORK (area treball): 0xBA00
;;
ASSETS_BANK_CFG_DEFAULT = 0xC0

ASSETS_FDC_BUF          = 0xBC00   ;; 512 bytes: buffer sector en RAM base
ASSETS_FDC_WORK         = 0xBE00   ;; 16 bytes: area treball en RAM base
NAU_FDC_RESULT          = ASSETS_FDC_WORK
NAU_FDC_DRIVE           = ASSETS_FDC_WORK + 8
NAU_FDC_CURTRACK        = ASSETS_FDC_WORK + 9
NAU_FDC_BLINK           = ASSETS_FDC_WORK + 10

;; Ports NEC 765 en CPC
FDC_MOTOR_PORT          = 0xFA7E
FDC_STATUS_PORT         = 0xFB7E
FDC_DATA_PORT           = 0xFB7F

;; Codis de comanda NEC 765
FDC_CMD_READ_DATA       = 0x46
FDC_CMD_SEEK            = 0x0F
FDC_CMD_RECALIBRATE     = 0x07
FDC_CMD_SENSE_INT       = 0x08

;; HOLD musica ISR (_g_mus_hold del GAME, via EQU fdc_hold.s):
;; PROPIETAT SIMETRICA: el motor l'activa en entrar NOMES si dest==C1
;; (player/canco en us) i el neteja en sortir (exit + fail) NOMES si
;; dest==C1. Mai toca mutes manuals del caller (caller: mus_stop()+
;; HOLD=1 ... lectures ... HOLD=0+mus_init(); necessari perque AKG Play
;; reprendria el so al tick seguent del mus_stop: el mute sol no es
;; enganxos). En C0/4/5/7 muts la ISR queda congelada (no Play) i la
;; musica NO fa soroll durant la lectura.

        .area _CODE

;; ============================================================
;; Bank switching
;; ============================================================

_assets_bank_select::
        ld a, (_g_fdc_dest_bank)
        ld (GBANK_ADDR), a      ;; _g_bank PRIMER (invariant bank_set):
                                ;; la ISR llegeix-restaura be si niua aqui
        ld bc, #0x7F00
        out (c), a
        ret

_assets_bank_restore::
        ld      a, (_g_fdc_home_bank) ;; home del caller (byte dedicat del
                                    ;; shim; lectura idempotent, sense estat)
        ld      (GBANK_ADDR), a ;; _g_bank PRIMER (mateix invariant)
        ld      bc, #0x7F00
        out     (c), a              ;; restaura el banc del CALLER (C0 central,
                                    ;; C4 FRONT futur)
        ret

;; ============================================================
;; _assets_fdc_load_generic
;; Retorna L=1 (OK) o L=0 (error)
;; Usa les variables globals _g_fdc_* configurades per C
;; ============================================================
_assets_fdc_load_generic::
        push ix
        di
        ;; HOLD nomes si dest==C1 (player/canco en us: sobreescriure'ls
        ;; sonant = crash). En C0/4/5/7 la ISR niua segura: el motor mante
        ;; _g_bank (invariant) i la musica CONTINUA durant la lectura.
        ld      a, (_g_fdc_dest_bank)
        cp      #0xC1
        jr      nz, hold_skip$
        ld      a, #1
        ld      (MUS_HOLD), a     ;; musica ISR en pausa (lectura en curs)
hold_skip$:

        ;; Fixar mapa RAM/ROM per defecte (upper ROM off, lower ROM off).
        ;; CRÍTIC: sense això, la upper ROM (AMSDOS) pot estar paginada
        ;; i interferir amb l'accés als ports FDC.
        ld a, (_g_fdc_home_bank)
        ld (GBANK_ADDR), a       ;; _g_bank = home PRIMER (mateix invariant)
        ld bc, #0x7F00
        out (c), a

        ;; Drive 0
        xor a
        ld (NAU_FDC_DRIVE), a

        ;; Motor ON + delay
        call nau_fdc_motor_on_delay

        ;; Buidar FDC: drenar bytes pendents + SENSE_INT per netejar
        call assets_fdc_drain
        call assets_fdc_flush

        ;; Recalibrate
        call nau_fdc_recalibrate
        jp nz, assets_fail_recal

        ;; Inicialitzar estat del stream
        ld hl, (_g_fdc_ondisk_bytes)
        ld a, l
        ld (assets_rem), a
        ld a, h
        ld (assets_rem_hi), a

        ld a, #128              ;; Sempre saltem header AMSDOS
        ld (assets_hdr_skip), a

        ld hl, (_g_fdc_dest_addr)
        ld a, l
        ld (assets_dst), a
        ld a, h
        ld (assets_dst_hi), a

        ld hl, (_g_fdc_chs_table)
        ld a, l
        ld (assets_tbl_lo), a
        ld a, h
        ld (assets_tbl_hi), a

        ld a, (_g_fdc_sector_count)
        ld (assets_sectors_left), a

assets_sector_loop:
        ld a, (assets_sectors_left)
        or a
        jr z, assets_load_done
        dec a
        ld (assets_sectors_left), a

        ;; Llegir (track, sid) de la taula CHS (parelles; head sempre 0,
        ;; dieta: 1 B per sector fora de les taules)
        ld a, (assets_tbl_lo)
        ld l, a
        ld a, (assets_tbl_hi)
        ld h, a
        ld b, (hl)              ;; B = track
        inc hl
        ld c, (hl)              ;; C = sector ID
        inc hl
        ld a, l
        ld (assets_tbl_lo), a
        ld a, h
        ld (assets_tbl_hi), a

        ;; Llegir sector al buffer FDC (512 bytes)
        ld de, #ASSETS_FDC_BUF
        call nau_fdc_read_phys_sector
        jp nz, assets_fail_sector

        ;; Stream: copiar bytes al banc, saltant header AMSDOS
        ld hl, #ASSETS_FDC_BUF
        call assets_stream_sector
        jr assets_sector_loop

assets_load_done:
        xor a
        ld bc, #FDC_MOTOR_PORT
        out (c), a
        ei
        ld a, (_g_fdc_dest_bank)
        cp #0xC1
        jr nz, holdkeep$
        xor a
        ld (MUS_HOLD), a          ;; neteja simetrica: nomes si l'haviem posat
holdkeep$:
        ld a, #1
        ld l, a
        pop ix
        ret

assets_fail_sector:
assets_fail_recal:
assets_fail_banked:
assets_fail:
        xor a
        ld bc, #FDC_MOTOR_PORT
        out (c), a
        call _assets_bank_restore  ;; restaura home fins i tot en error
        ei                         ;; (callers banked hi sobreviuen; central,
                                    ;; identic a abans: home=C0)
        ld a, (_g_fdc_dest_bank)
        cp #0xC1
        jr nz, holdkeep2$
        xor a
        ld (MUS_HOLD), a          ;; neteja simetrica fins i tot en error
holdkeep2$:
        xor a
        ld l, a
        pop ix
        ret

;; ============================================================
;; assets_stream_sector
;; HL = ASSETS_FDC_BUF (512 bytes a processar)
;; Copia bytes al banc en ASSETS_BANK_ADDR, saltant els
;; primers assets_hdr_skip bytes (header AMSDOS = 128).
;; assets_rem: bytes restants a copiar (decreix fins 0).
;; assets_dst: adresa destí al banc (increix).
;; Igual que transit_stream_sector de nau_transit.s.
;; ============================================================
assets_stream_sector:
        ;; Comprova si ja hem acabat tot el fitxer
        ld a, (assets_rem)
        ld e, a
        ld a, (assets_rem_hi)
        or e
        ret z                   ;; Retorna si no queden bytes per copiar

        ;; CRÍTIC: desactivar interrupts abans del bank-select.
        ;; nau_fdc_read_phys_sector fa un 'ei' intern a la result phase,
        ;; trencant el 'di' global de _assets_fdc_load_generic.
        ;; Si la ISR del BIOS del CPC 6128 escriu al Gate Array (mode/ROM),
        ;; pot resetejar el banc a 0xC0 (VRAM) entremig de la còpia de bytes.
        di

        ;; Commutar al banc expandit de destinació abans d'iniciar la còpia del sector
        push bc
        call _assets_bank_select
        pop bc

        ld bc, #512
assets_ss_lp:
        ;; Comprova si hem acabat durant la còpia del sector
        ld a, (assets_rem)
        ld e, a
        ld a, (assets_rem_hi)
        or e
        jr z, assets_ss_done

        ;; Saltar header AMSDOS?
        ld a, (assets_hdr_skip)
        or a
        jr z, assets_ss_copy
        dec a
        ld (assets_hdr_skip), a
        inc hl
        jr assets_ss_dec

assets_ss_copy:
        ld e, (hl)
        inc hl
        push hl
        ld a, (assets_dst)
        ld l, a
        ld a, (assets_dst_hi)
        ld h, a
        
        ;; Escriure directament (el banc ja està actiu)
        ld (hl), e
        inc hl
        
        ld a, l
        ld (assets_dst), a
        ld a, h
        ld (assets_dst_hi), a
        pop hl

assets_ss_dec:
        ;; Decrementar REM (16-bit)
        ld a, (assets_rem)
        ld e, a
        ld a, (assets_rem_hi)
        ld d, a
        dec de
        ld a, e
        ld (assets_rem), a
        ld a, d
        ld (assets_rem_hi), a
        
        dec bc
        ld a, b
        or c
        jr nz, assets_ss_lp

assets_ss_done:
        ;; Parpelleig LED / etiqueta del disquet a cada sector FDC llegit (Màxim contrast Groc 0x4A <-> Negre 0x54)
        ld      a, (NAU_FDC_BLINK)
        bit     7, a
        jr      nz, 3$              ;; Si bit 7 actiu (0x80), no commutar paleta (silenci visual total)
        push    bc
        push    af
        ld      bc, #0x7F00
        ld      a, #0x02            ;; Seleccionar Ink 2 (Groc / LED)
        out     (c), a
        ld      a, (NAU_FDC_BLINK)
        xor     #0x01
        ld      (NAU_FDC_BLINK), a
        jr      z, 1$
        ld      a, #0x4A            ;; Groc daurat brillant (LED ON)
        out     (c), a
        jr      2$
1$:
        ld      a, #0x54            ;; Negre apagat (LED OFF)
        out     (c), a
2$:
        pop     af
        pop     bc
3$:
        ;; Restaurar la RAM base normal (0xC0) al final de la còpia del sector
        push    bc
        call    _assets_bank_restore
        pop bc
        ;; Reactivar interrupts ara que el banc esta restaurat a 0xC0 (RAM base segura)
        ei
        ret

;; ============================================================
;; Rutines FDC (copia exacta de nau_fdc_low.inc — codi provat)
;; ============================================================

;; Buidar bytes pendents si el FDC esta en result phase (DIO=1).
assets_fdc_drain:
        ld bc, #FDC_STATUS_PORT
assets_fdc_drain_lp:
        in a, (c)
        and #0xC0
        cp #0xC0            ;; RQM=1, DIO=1? (FDC vol donar dades)
        ret nz              ;; No -> FDC net
        inc c
        in a, (c)           ;; Llegir i descartar byte
        dec c
        jr assets_fdc_drain_lp

;; Buidar FDC: fins 4 SENSE_INT per netejar interrupcions pendents.
;; Ignora el resultat — simplement buida la cua del FDC.
assets_fdc_flush:
        ld b, #4
assets_fdc_flush_loop:
        push bc
        ld a, #FDC_CMD_SENSE_INT
        call nau_fdc_write_cmd_byte
        call nau_fdc_result_phase
        pop bc
        djnz assets_fdc_flush_loop
        ret

nau_fdc_motor_on_delay:
        ld bc, #FDC_MOTOR_PORT
        ld a, #1
        out (c), a
        ld b, #0x04
nau_fdc_mdelay_o:
        ld de, #0x0000
nau_fdc_mdelay_i:
        dec de
        ld a, d
        or e
        jr nz, nau_fdc_mdelay_i
        djnz nau_fdc_mdelay_o
        ret

;; Byte de comanda/parametre en A
;; Si DIO=1 (FDC vol donar dades), retorna sense escriure (identic nau_fdc_low.inc).
nau_fdc_write_cmd_byte:
        push af
        ld bc, #FDC_STATUS_PORT
nau_fdc_wcb1:
        in a, (c)
        add a, a
        jr nc, nau_fdc_wcb1
        add a, a
        jr nc, nau_fdc_wcb2
        pop af
        ret
nau_fdc_wcb2:
        pop af
        inc c
        out (c), a
        dec c
        ld a, #5
nau_fdc_wcbd:
        dec a
        jr nz, nau_fdc_wcbd
        ret

nau_fdc_result_phase:
        ld hl, #NAU_FDC_RESULT
        ld bc, #FDC_STATUS_PORT
nau_fdc_res1:
        in a, (c)
        cp #0xC0
        jr c, nau_fdc_res1
        inc c
        in a, (c)
        dec c
        ld (hl), a
        inc hl
        ld a, #5
nau_fdc_resd:
        dec a
        jr nz, nau_fdc_resd
        in a, (c)
        and #0x10
        jr nz, nau_fdc_res1
        ret

;; NZ = cal repetir seek/recal (error seek o no "seek complete")
;; Identic a nau_fdc_low.inc (naudx, provat en hardware).
nau_fdc_seek_wait:
        ld a, #FDC_CMD_SENSE_INT
        call nau_fdc_write_cmd_byte
        call nau_fdc_result_phase
        ld ix, #NAU_FDC_RESULT
        bit 5, 0(ix)
        jr z, nau_fdc_seek_wait
        bit 4, 0(ix)
        ret

nau_fdc_recalibrate:
nau_fdc_recal_r:
        ld a, #FDC_CMD_RECALIBRATE
        call nau_fdc_write_cmd_byte
        ld a, (NAU_FDC_DRIVE)
        call nau_fdc_write_cmd_byte
        call nau_fdc_seek_wait
        jr nz, nau_fdc_recal_r
        ret

;; Usa NAU_FDC_CURTRACK (omplert pel caller)
nau_fdc_seek_track:
nau_fdc_seek_r:
        ld a, #FDC_CMD_SEEK
        call nau_fdc_write_cmd_byte
        ld a, (NAU_FDC_DRIVE)
        call nau_fdc_write_cmd_byte
        ld a, (NAU_FDC_CURTRACK)
        call nau_fdc_write_cmd_byte
        call nau_fdc_seek_wait
        jr nz, nau_fdc_seek_r
        ret

;; Entrada: B=track fisic, C=ID sector (0xC1-0xC9), DE=desti (512 bytes)
nau_fdc_read_phys_sector:
        ld a, b
        ld (NAU_FDC_CURTRACK), a
        push bc
        push de
        call nau_fdc_seek_track
        pop de
        pop bc
        ld l, c
        ld a, #FDC_CMD_READ_DATA
        call nau_fdc_write_cmd_byte
        ld a, (NAU_FDC_DRIVE)
        call nau_fdc_write_cmd_byte
        ld a, (NAU_FDC_CURTRACK)
        call nau_fdc_write_cmd_byte
        xor a
        call nau_fdc_write_cmd_byte
        ld a, l
        call nau_fdc_write_cmd_byte
        ld a, #2
        call nau_fdc_write_cmd_byte
        ld a, l
        call nau_fdc_write_cmd_byte
        ld a, #0x2A
        call nau_fdc_write_cmd_byte
        ld a, #0xFF
        call nau_fdc_write_cmd_byte
        di
        ld bc, #FDC_STATUS_PORT
        push de
        pop hl                  ;; HL = destí
        ld de, #512             ;; N=2 => 512 bytes exactes
nau_fdc_rdlp:
        in a, (c)
        jp p, nau_fdc_rdlp
        and #0x20
        jp z, nau_fdc_rdend_early
        inc c
        in a, (c)
        ld (hl), a
        dec c
        inc hl
        dec de
        ld a, d
        or e
        jp nz, nau_fdc_rdlp
        jp nau_fdc_rdend
nau_fdc_rdend_early:
        ;; Si el FDC talla abans de 512 bytes, tractar-ho igualment via result phase.
nau_fdc_rdend:
        ei
        call nau_fdc_result_phase
        ld ix, #NAU_FDC_RESULT
        ld a, 0(ix)
        and #0xC0               ;; IC=00: normal termination
        ret z
        ld a, 0(ix)
        cp #0x40                ;; Cas CPC/nau: abnormal + EndOfCylinder
        ret nz
        ld a, 1(ix)
        cp #0x80
        ret

        .area _DATA
assets_sectors_left:    .ds 1
assets_rem:             .ds 1
assets_rem_hi:          .ds 1
assets_hdr_skip:        .ds 1
assets_dst:             .ds 1
assets_dst_hi:          .ds 1
assets_tbl_lo:          .ds 1
assets_tbl_hi:          .ds 1
