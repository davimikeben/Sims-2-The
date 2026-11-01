#!/usr/bin/env python3
"""
Converte um ISO de PS2 em CSO (CSOv1, deflate raw por bloco) e confere se o
emulador vai RECONHECER o disco.

Formato implementado espelhando o leitor do emulador
(`pcsx2/CDVD/CsoFileReader.cpp`, que segue o README_CSO do maxcso):

  header (24 bytes = 0x18):
     magic[4]  = b"CISO"
     u32 header_size = 0x18
     u64 total_bytes = tamanho do ISO
     u32 frame_size  = 2048 (potencia de 2, >= 2048)
     u8  ver         = 1
     u8  align       = shift dos offsets (bytes = index << align)
     u8  reserved[2] = 0
  indice: (numFrames + 1) x u32 LE
     bit31 = 1 -> bloco ARMAZENADO CRU (frame_size bytes)
     bits 0..30 -> posicao ABSOLUTA do bloco no arquivo, em unidades de (1<<align)
  payload: blocos deflate raw (windowBits=-15)

O leitor exige `total_out == frame_size` em cada frame, por isso o ISO precisa
ter tamanho multiplo de 2048 (validado aqui).

Depois de gerar, o script decodifica o CSO e checa duas coisas:
  1. round-trip: o CSO reconstroi o ISO byte a byte (sha256);
  2. "o emulador reconhece o disco": cabeçalho/índice como o CsoFileReader lê,
     PVD na trilha 16 com "CD001" + "PLAYSTATION" e SYSTEM.CNF com BOOT2 -> sem
     isso o BIOS para na tela "Inserir um disco com o formato para PlayStation
     ou PlayStation 2".

Uso:
  python3 tools/iso_to_cso.py entrada.iso saida.cso [--level 1] [--frame 2048]
  python3 tools/iso_to_cso.py --check jogo.cso      # audita um CSO já pronto
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import tempfile
import time
import zlib

FRAME = 2048
SECTOR = 2048
HEADER_SIZE = 0x18
PLAYSTATION_ID = b"PLAYSTATION"


class DiscCheckError(Exception):
    """O emulador/BIOS não vai aceitar este disco."""


def choose_align(max_offset: int) -> int:
    """Offsets sao u31 (bit31 = flag). Acima de 2 GiB dividimos por potencia de 2."""
    align = 0
    while (max_offset >> align) >= 0x80000000:
        align += 1
    return align


def compress_iso(iso_path: str, cso_path: str, level: int = 1, log=print,
                 frame: int = FRAME) -> dict:
    size = os.path.getsize(iso_path)
    if size % frame != 0:
        raise SystemExit(
            f"ISO com {size} bytes nao e multiplo de {frame}: o leitor do emulador "
            f"falharia no ultimo frame.")
    num_frames = size // frame
    log(f"ISO: {os.path.basename(iso_path)} "
        f"({size/1048576:.1f} MB, {num_frames} frames de {frame} B)")

    payload = tempfile.NamedTemporaryFile(delete=False, suffix=".payload")
    offsets = [0] * (num_frames + 1)
    written = 0
    stored_raw = 0
    t0 = time.time()
    chunk_frames = max(1, (8 * 1024 * 1024) // frame)

    with open(iso_path, "rb", buffering=0) as fin, payload as fout:
        idx = 0
        while True:
            buf = fin.read(frame * chunk_frames)
            if not buf:
                break
            for off in range(0, len(buf), frame):
                block = buf[off:off + frame]
                comp = zlib.compress(block, level, wbits=-15)
                if len(comp) >= frame:
                    offsets[idx] = written | 0x80000000
                    fout.write(block)
                    written += frame
                    stored_raw += 1
                else:
                    offsets[idx] = written
                    fout.write(comp)
                    written += len(comp)
                idx += 1
            done = idx * frame
            log(f"  {done*100/size:5.1f}%  {done/max(1e-6, time.time()-t0)/1048576:6.1f} MB/s"
                f"  saida {written/1048576:7.1f} MB")
        offsets[num_frames] = written

    # Os offsets do indice sao ABSOLUTOS no arquivo (o leitor faz FSeek64 direto),
    # nao relativos ao inicio do payload.
    base = HEADER_SIZE + 4 * (num_frames + 1)
    offsets = [((v & 0x80000000) | (base + (v & 0x7FFFFFFF)))
               for v in offsets]
    written += base

    align = choose_align(written)
    if align:
        # Com align>0 cada bloco precisaria comecar num multiplo de (1<<align).
        # Nosso CSO fica < 2 GiB, entao isso nao deve acontecer; falhar e melhor
        # do que gerar arquivo corrompido em silencio.
        raise SystemExit(
            f"CSO passaria de 2 GiB (offsets u31): align={align} nao implementado")

    with open(cso_path, "wb") as dst:
        dst.write(b"CISO")
        dst.write(struct.pack("<I", HEADER_SIZE))
        dst.write(struct.pack("<Q", size))
        dst.write(struct.pack("<I", frame))
        dst.write(struct.pack("<B", 1))
        dst.write(struct.pack("<B", align))
        dst.write(b"\x00\x00")
        assert dst.tell() == HEADER_SIZE
        for v in offsets:
            dst.write(struct.pack("<I", (v & 0x80000000) | ((v & 0x7FFFFFFF) >> align)))
        with open(payload.name, "rb") as src:
            for b in iter(lambda: src.read(8 * 1024 * 1024), b""):
                dst.write(b)
    os.unlink(payload.name)

    out_size = os.path.getsize(cso_path)
    log(f"CSO: {os.path.basename(cso_path)} ({out_size/1048576:.1f} MB)  "
        f"compressao {size/out_size:.2f}x  blocos crus {stored_raw}  "
        f"tempo {time.time()-t0:.0f}s")
    return {"iso_size": size, "cso_size": out_size, "frames": num_frames,
            "raw_blocks": stored_raw, "align": align}

# --------------------------------------------------------------------------- #
#  Leitor de conferencia: reproduz o CsoFileReader do emulador passo a passo
# --------------------------------------------------------------------------- #

class CsoDecoder:
    """Mesma leitura de `CsoFileReader::ReadChunk` (offsets absolutos + shift)."""

    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "rb")
        self.file_size = os.path.getsize(path)
        raw = self.f.read(HEADER_SIZE)
        if len(raw) != HEADER_SIZE:
            raise DiscCheckError(
                f"{os.path.basename(path)} tem {self.file_size} B: nem o cabecalho (24 B) cabe")
        (self.magic, self.header_size, self.total, self.frame,
         self.ver, self.align, _reserved) = struct.unpack("<4sIQIBB2s", raw)
        if self.frame <= 0:
            raise DiscCheckError("frame_size = 0 no cabecalho")
        self.num = (self.total + self.frame - 1) // self.frame
        self.data_off = HEADER_SIZE + 4 * (self.num + 1)
        index_raw = self.f.read(4 * (self.num + 1))
        if len(index_raw) != 4 * (self.num + 1):
            raise DiscCheckError(
                f"indice truncado: {len(index_raw)} B de {4 * (self.num + 1)} B "
                f"(cabecalho diz {self.num} frames de {self.frame} B)")
        self.index = list(struct.unpack(f"<{self.num + 1}I", index_raw))

    # -- o que o leitor do emulador valida em ValidateHeader + InitializeBuffers --
    def validate(self) -> dict:
        if self.magic not in (b"CISO", b"ZISO"):
            raise DiscCheckError(
                f"magic {self.magic!r}: o emulador so aceita CISO/ZISO (arquivo nao e CSO)")
        if self.ver > 1:
            raise DiscCheckError(f"ver {self.ver}: o emulador so le CSOv1")
        if self.frame < SECTOR or (self.frame & (self.frame - 1)):
            raise DiscCheckError(
                f"frame_size {self.frame}: precisa ser potencia de 2 e >= {SECTOR}")

        first = (self.index[0] & 0x7FFFFFFF) << self.align
        if first != self.data_off:
            raise DiscCheckError(
                f"indice[0] = {first} mas o payload comeca em {self.data_off}: os offsets "
                "do indice tem de ser ABSOLUTOS no arquivo (era o bug do 'inserir disco')")
        last = (self.index[-1] & 0x7FFFFFFF) << self.align
        if last != self.file_size:
            raise DiscCheckError(
                f"indice[last] = {last} != tamanho do arquivo ({self.file_size}): "
                "CSO truncado ou indice incompleto")

        prev = 0
        for i, value in enumerate(self.index):
            pos = (value & 0x7FFFFFFF) << self.align
            if pos < prev:
                raise DiscCheckError(f"offset fora de ordem no indice[{i}]")
            prev = pos

        for i in range(self.num):
            if self.index[i] & 0x80000000:
                size = (((self.index[i + 1] & 0x7FFFFFFF)
                         - (self.index[i] & 0x7FFFFFFF)) << self.align)
                if size != self.frame:
                    raise DiscCheckError(
                        f"frame {i} esta marcado como cru (bit31) mas ocupa {size} B "
                        f"em vez de {self.frame} B")

        return {"frames": self.num, "frame": self.frame, "align": self.align,
                "total": self.total, "data_off": self.data_off,
                "raw_blocks": sum(1 for v in self.index[:-1] if v & 0x80000000)}

    def frame_at(self, i: int) -> bytes:
        """Mesma logica de CsoFileReader::ReadChunk."""
        e0, e1 = self.index[i], self.index[i + 1]
        compressed = (e0 & 0x80000000) == 0
        pos = (e0 & 0x7FFFFFFF) << self.align
        end = (e1 & 0x7FFFFFFF) << self.align
        self.f.seek(pos)   # absoluto, igual a CsoFileReader::ReadChunk
        raw = self.f.read(end - pos)
        if not compressed:
            return raw
        out = zlib.decompressobj(-15).decompress(raw)
        if len(out) != self.frame:
            raise DiscCheckError(f"frame {i}: {len(out)} bytes (esperado {self.frame})")
        return out

    def read_at(self, offset: int, length: int) -> bytes:
        """Leitura por byte (o leitor do emulador entrega setores de 2048)."""
        out = bytearray()
        while length > 0:
            i = offset // self.frame
            within = offset % self.frame
            if i >= self.num:
                break
            data = self.frame_at(i)
            chunk = min(length, self.frame - within)
            out += data[within:within + chunk]
            offset += chunk
            length -= chunk
        return bytes(out)

    def sector(self, lba: int) -> bytes:
        return self.read_at(lba * SECTOR, SECTOR)

    def verify(self, log=print) -> str:
        h = hashlib.sha256()
        t0 = time.time()
        for i in range(self.num):
            h.update(self.frame_at(i))
            if i and i % 250000 == 0:
                log(f"  verificando {i*100//self.num}%...")
        log(f"  verificado em {time.time()-t0:.0f}s")
        return h.hexdigest()

    def close(self) -> None:
        self.f.close()

# --------------------------------------------------------------------------- #
#  "O emulador reconhece este disco?" - mesmos testes que o BIOS faz
# --------------------------------------------------------------------------- #

def _le32(buf: bytes) -> int:
    return struct.unpack("<I", buf[:4])[0]


def _dir_entries(dec: CsoDecoder, lba: int, length: int) -> list:
    """Percorre um diretorio ISO9660 (registros de tamanho variavel, setor a setor)."""
    data = dec.read_at(lba * SECTOR, length)
    entries = []
    off = 0
    while off < min(length, len(data)):
        rec_len = data[off]
        if rec_len == 0:                      # fim do setor: pula para o proximo
            off = (off // SECTOR + 1) * SECTOR
            continue
        name_len = data[off + 32]
        entries.append((
            data[off + 33:off + 33 + name_len].decode("latin-1"),
            _le32(data[off + 2:off + 6]),      # LBA do conteudo
            _le32(data[off + 10:off + 14]),    # tamanho
            data[off + 25],                    # flags (bit 1 = diretorio)
        ))
        off += rec_len
    return entries


def disc_info(dec: CsoDecoder) -> dict:
    """Reproduz o que o emulador + o BIOS exigem para aceitar o disco.

    O emulador (InputIsoFile::tryIsoType) le a trilha 16 e exige "CD001"; o BIOS do
    PS2 vai alem e exige o system id "PLAYSTATION" e o SYSTEM.CNF com BOOT2. Faltando
    qualquer um, o console para em "Inserir um disco com o formato para PlayStation ou
    PlayStation 2".
    """
    pvd = dec.sector(16)
    if len(pvd) != SECTOR:
        raise DiscCheckError("disco menor que 17 setores: nao tem trilha 16 (PVD)")
    if pvd[0] != 1:
        raise DiscCheckError(
            f"trilha 16 nao e um Primary Volume Descriptor (tipo {pvd[0]})")
    if pvd[1:6] != b"CD001":
        raise DiscCheckError(
            f"trilha 16 sem \"CD001\" (achei {pvd[1:6]!r}): o emulador nao identifica o disco")
    system_id = pvd[8:40].rstrip(b" \x00")
    if not system_id.startswith(PLAYSTATION_ID):
        raise DiscCheckError(
            f"system id {system_id!r} != PLAYSTATION: o BIOS recusa o disco")
    block_size = struct.unpack("<H", pvd[128:130])[0]
    if block_size != SECTOR:
        raise DiscCheckError(f"logical block size {block_size} != {SECTOR}")

    volume_id = pvd[40:72].rstrip(b" \x00").decode("latin-1")
    volume_space = _le32(pvd[80:84])
    root = pvd[156:190]
    root_lba, root_len = _le32(root[2:6]), _le32(root[10:14])
    entries = _dir_entries(dec, root_lba, root_len)
    if not entries:
        raise DiscCheckError("diretorio raiz vazio")
    table = {}
    for name, lba, size, flags in entries:
        table[name.upper().split(";")[0]] = (name, lba, size, flags)

    if "SYSTEM.CNF" not in table:
        raise DiscCheckError(
            "disco sem SYSTEM.CNF: o BIOS mostra \"Inserir um disco com o formato para "
            "PlayStation ou PlayStation 2\" (imagem ruim/scrubada)")
    cnf_name, cnf_lba, cnf_size, _ = table["SYSTEM.CNF"]
    cnf = dec.read_at(cnf_lba * SECTOR, cnf_size)
    text = cnf.decode("latin-1", "replace")

    boot2 = ""
    vmode = ""
    for line in text.splitlines():
        key, _, value = line.partition("=")
        key = key.strip().upper()
        if key == "BOOT2":
            boot2 = value.strip()
        elif key == "VMODE":
            vmode = value.strip()
    if not boot2:
        raise DiscCheckError(
            f"SYSTEM.CNF sem BOOT2 (o BIOS nao sabe o que executar):\n{text.strip()}")

    exe_name = boot2.split(":")[-1].lstrip("\\/").strip()
    exe_key = exe_name.split(";")[0].upper()
    if exe_key not in table:
        raise DiscCheckError(
            f"BOOT2 aponta para {exe_name!r}, que nao existe no diretorio raiz do disco")
    _, exe_lba, exe_size, _ = table[exe_key]
    if exe_size <= 0:
        raise DiscCheckError(f"o executavel {exe_name} tem 0 byte")

    return {
        "system_id": system_id.decode("latin-1"),
        "volume_id": volume_id,
        "volume_space": volume_space,
        "boot2": boot2,
        "exe": exe_name.split(";")[0],
        "exe_size": exe_size,
        "vmode": vmode,
        "files": len(entries),
    }


def audit_cso(path: str, deep: bool = True, log=print) -> dict:
    """Valida um CSO como o emulador faria (e, opcionalmente, decodifica tudo)."""
    dec = CsoDecoder(path)
    try:
        log(f"CSO: {os.path.basename(path)} ({dec.file_size/1048576:.1f} MB)")
        info = dec.validate()
        log(f"  cabecalho + indice ...... ok   {info['frames']} frames de {info['frame']} B"
            f" ({info['raw_blocks']} crus), align {info['align']}")
        disc = disc_info(dec)
        log(f"  trilha 16 (PVD) ......... ok   {disc['system_id']}, volume {disc['volume_id']}")
        log(f"  SYSTEM.CNF / BOOT2 ...... ok   {disc['boot2']}"
            + (f"  ({disc['vmode']})" if disc['vmode'] else ""))
        digest = None
        if deep:
            t0 = time.time()
            digest = dec.verify(log=log)
            log(f"  todos os {info['frames']} frames .. ok   em {time.time()-t0:.0f}s")
        return {"structure": info, "disc": disc, "sha256": digest}
    finally:
        dec.close()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="ISO -> CSO de PS2 (e conferencia de que o emulador reconhece o disco)")
    ap.add_argument("iso", nargs="?", help="ISO de entrada")
    ap.add_argument("cso", nargs="?", help="CSO de saida")
    ap.add_argument("--check", metavar="CSO", help="so audita um CSO existente")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--frame", type=int, default=FRAME)
    ap.add_argument("--no-verify", action="store_true",
                    help="nao compara o sha256 com o ISO de origem")
    ap.add_argument("--no-boot-check", action="store_true",
                    help="nao checa PVD/SYSTEM.CNF (imagem que nao e de PS1/PS2)")
    args = ap.parse_args()

    if args.check:
        try:
            res = audit_cso(args.check, deep=True)
        except DiscCheckError as e:
            raise SystemExit(f"FALHOU: {e}")
        print("OK: o emulador reconhece este disco (frame 16 + SYSTEM.CNF)")
        print("sha256 do ISO reconstruido:", res["sha256"])
        return

    if not (args.iso and args.cso):
        ap.error("informe entrada.iso e saida.cso (ou use --check arquivo.cso)")

    info = compress_iso(args.iso, args.cso, args.level, frame=args.frame)
    print(info)

    try:
        res = audit_cso(args.cso, deep=not args.no_verify)
    except DiscCheckError as e:
        raise SystemExit(f"FALHOU: {e}")

    if args.no_boot_check:
        pass
    else:
        print(f"OK: disco de PS2 valido -> {res['disc']['boot2']}")

    if not args.no_verify:
        want = sha256_of(args.iso)
        print("iso", want)
        print("cso", res["sha256"])
        if res["sha256"] != want:
            raise SystemExit("FALHOU: CSO nao reconstroi o ISO")
        print("OK: CSO reconstroi o ISO byte a byte")


if __name__ == "__main__":
    main()
