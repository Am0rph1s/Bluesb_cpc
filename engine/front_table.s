    .module front_table
    .globl _front_run
    .area _CODE
;; Slot unic a FRONT_BASE: el caller central fa bank_set(C4) + CALL
;; absoluta (el build verifica que l'entry es FRONT_BASE).
_front_entry::
    jp      _front_run
_front_map_entry::
    jp      _front_map
