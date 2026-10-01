#!/usr/bin/env python3
"""
dskutil.py - Creacio i farcit de DSK CPC (format MV-CPCEMU) sense iDSK.
Portat de fix_dsk.py / build_master_game.py de Desperta Ferro.
"""

TRACK_HDR   = 256
SECTOR_SIZE = 512
SECTORS_PT  = 9
# Ordre LOGIC dels sector IDs (com AMSDOS mappa blocs a sectors)
LOGICAL_IDS = [0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9]
# Ordre FISIC d'intercalat estandard CPC
INTERLEAVE  = [0xC1, 0xC6, 0xC2, 0xC7, 0xC3, 0xC8, 0xC4, 0xC9, 0xC5]


def amsdos_header(name8, ext3, ftype, load_addr, exec_addr, data_size):
    """Construeix la capcalera AMSDOS de 128 bytes d'un fitxer binari."""
    h = bytearray(128)
    for i, c in enumerate(name8.ljust(8)[:8].encode()):
        h[0x01 + i] = c
    for i, c in enumerate(ext3.ljust(3)[:3].encode()):
        h[0x09 + i] = c
    h[0x12] = ftype
    h[0x15] = load_addr & 0xFF
    h[0x16] = (load_addr >> 8) & 0xFF
    h[0x18] = data_size & 0xFF
    h[0x19] = (data_size >> 8) & 0xFF
    h[0x1A] = exec_addr & 0xFF
    h[0x1B] = (exec_addr >> 8) & 0xFF
    real = 128 + data_size
    h[0x40] = real & 0xFF
    h[0x41] = (real >> 8) & 0xFF
    chk = sum(h[:0x43]) & 0xFFFF
    h[0x43] = chk & 0xFF
    h[0x44] = (chk >> 8) & 0xFF
    return bytes(h)


def create_empty_cpc_dsk(path, num_tracks=40):
    """Crea un DSK buit de 40 pistes 1 cara, 9 sectors, amb intercalat fisic."""
    dsk = bytearray(256)
    sig = b'MV - CPCEMU Disk-File\r\nDisk-Info\r\n'
    dsk[:len(sig)] = sig
    dsk[0x30] = num_tracks
    dsk[0x31] = 1
    track_size = TRACK_HDR + SECTORS_PT * SECTOR_SIZE
    dsk[0x32] = track_size & 0xFF
    dsk[0x33] = (track_size >> 8) & 0xFF
    for t in range(num_tracks):
        th = bytearray(256)
        tsig = b'Track-Info\r\n'
        th[:len(tsig)] = tsig
        th[0x10] = t
        th[0x11] = 0
        th[0x14] = 2
        th[0x15] = SECTORS_PT
        th[0x16] = 0x4E
        th[0x17] = 0xE5
        for i, sid in enumerate(INTERLEAVE):
            off = 0x18 + i * 8
            th[off + 0] = t
            th[off + 1] = 0
            th[off + 2] = sid
            th[off + 3] = 2
            th[off + 4] = 0
            th[off + 5] = 0
            th[off + 6] = 0
            th[off + 7] = 2
        dsk += th
        dsk += b'\xE5' * (SECTORS_PT * SECTOR_SIZE)
    with open(path, 'wb') as f:
        f.write(dsk)


class DskPatcher:
    """Llegeix i modifica un DSK en format MV-CPCEMU (estandard CPC)."""

    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = bytearray(f.read())
        hdr = self.data[:256]
        self.num_tracks = hdr[0x30]
        self.num_sides = hdr[0x31]
        self.track_size = hdr[0x32] + hdr[0x33] * 256

    def _track_offset(self, track, side=0):
        return 256 + (track * self.num_sides + side) * self.track_size

    def read_sector(self, track, sector_id):
        to = self._track_offset(track)
        th = self.data[to:to + TRACK_HDR]
        n = th[0x15]
        for s in range(n):
            off = 0x18 + s * 8
            if th[off + 2] == sector_id:
                so = to + TRACK_HDR + s * SECTOR_SIZE
                return bytearray(self.data[so:so + SECTOR_SIZE])
        return None

    def write_sector(self, track, sector_id, sector_data):
        to = self._track_offset(track)
        th = self.data[to:to + TRACK_HDR]
        n = th[0x15]
        for s in range(n):
            off = 0x18 + s * 8
            if th[off + 2] == sector_id:
                so = to + TRACK_HDR + s * SECTOR_SIZE
                self.data[so:so + SECTOR_SIZE] = sector_data[:SECTOR_SIZE]
                return True
        return False

    def read_dir_sectors(self):
        result = bytearray()
        for sid in [0xC1, 0xC2, 0xC3, 0xC4]:
            s = self.read_sector(0, sid)
            result += s if s else bytearray(512)
        return result

    def write_dir_sectors(self, dir_data):
        for i, sid in enumerate([0xC1, 0xC2, 0xC3, 0xC4]):
            self.write_sector(0, sid, dir_data[i * 512:(i + 1) * 512])

    def bloc_to_ts(self, bloc):
        abs_sec = bloc * 2
        result = []
        for i in range(2):
            s = abs_sec + i
            result.append((s // SECTORS_PT, LOGICAL_IDS[s % SECTORS_PT]))
        return result

    def write_file_data(self, start_bloc, data):
        written = 0
        bloc = start_bloc
        while written < len(data):
            chunk1 = (data[written:written + 512] + b'\xE5' * 512)[:512]
            chunk2 = (data[written + 512:written + 1024] + b'\xE5' * 512)[:512]
            ts = self.bloc_to_ts(bloc)
            if ts[0][0] < self.num_tracks:
                self.write_sector(ts[0][0], ts[0][1], chunk1)
            if ts[1][0] < self.num_tracks:
                self.write_sector(ts[1][0], ts[1][1], chunk2)
            written += 1024
            bloc += 1

    def add_file(self, cpm_name8, cpm_ext3, file_data_with_amsdos):
        """Afegeix un fitxer nou (capcalera AMSDOS inclosa) al directori i dades."""
        dir_data = bytearray(self.read_dir_sectors())
        n_blocs = (len(file_data_with_amsdos) + 1023) // 1024

        used = {0, 1}
        for i in range(64):
            e = dir_data[i * 32:(i + 1) * 32]
            if e[0] == 0:
                for j in range(16):
                    if e[16 + j]:
                        used.add(e[16 + j])
        start_bloc = 2
        while start_bloc in used:
            start_bloc += 1
        blocs = list(range(start_bloc, start_bloc + n_blocs))

        total_records = (len(file_data_with_amsdos) + 127) // 128
        extent_idx = 0
        rem_records = total_records
        rem_blocs = list(blocs)

        while rem_records > 0 and rem_blocs:
            rec_in_this_extent = min(128, rem_records)
            blocs_in_this_extent = rem_blocs[:16]

            for i in range(64):
                e = dir_data[i * 32:(i + 1) * 32]
                if e[0] == 0xE5:
                    entry = bytearray(32)
                    entry[0] = 0
                    for j, c in enumerate(cpm_name8.ljust(8)[:8].upper().encode()):
                        entry[1 + j] = c
                    for j, c in enumerate(cpm_ext3.ljust(3)[:3].upper().encode()):
                        entry[9 + j] = c
                    entry[12] = extent_idx & 0x1F
                    entry[14] = (extent_idx >> 5) & 0xFF
                    entry[15] = rec_in_this_extent
                    for j, b in enumerate(blocs_in_this_extent):
                        entry[16 + j] = b
                    dir_data[i * 32:(i + 1) * 32] = entry
                    break

            rem_records -= rec_in_this_extent
            rem_blocs = rem_blocs[16:]
            extent_idx += 1

        self.write_dir_sectors(dir_data)
        self.write_file_data(start_bloc, file_data_with_amsdos)
        return blocs

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.data)
