#!/usr/bin/env python3
"""
Converte um ISO de PS2 em CSO (CSOv1, deflate raw por bloco).

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
     bits 0..30 -> posicao do bloco, em unidades de (1 << align)
  payload: blocos deflate raw (windowBits=-15)

O leitor exige `total_out == frame_size` em cada frame, por isso o ISO precisa
ter tamanho multiplo de 2048 (validado aqui).

Uso:
  python3 tools/iso_to_cso.py entrada.iso saida.cso [--level 1]
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
HEADER_SIZE = 0x18


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

    align = choose_align(written)
    if align:
        log(f"aviso: offsets exigem align={align} (arquivo > 2 GiB)")

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
#  Decodificador de conferencia: reproduz o leitor C++ passo a passo
# --------------------------------------------------------------------------- #

class CsoDecoder:
    def __init__(self, path: str):
        self.f = open(path, "rb")
        hdr = self.f.read(HEADER_SIZE)
        magic, header_size, total, frame, ver, align, _ = struct.unpack("<4sIQIBB2s", hdr)
        if magic not in (b"CISO", b"ZISO"):
            raise SystemExit(f"magic invalido: {magic!r}")
        if header_size != HEADER_SIZE:
            raise SystemExit(f"header_size {header_size} != {HEADER_SIZE}")
        if ver > 1:
            raise SystemExit("ver > 1")
        if frame < 2048 or (frame & (frame - 1)):
            raise SystemExit("frame_size invalido")
        self.total, self.frame, self.align = total, frame, align
        self.num = (total + frame - 1) // frame
        raw = self.f.read(4 * (self.num + 1))
        self.index = list(struct.unpack(f"<{self.num + 1}I", raw))
        self.data_off = HEADER_SIZE + 4 * (self.num + 1)
        if (self.index[0] & 0x7FFFFFFF) != 0:
            raise SystemExit("primeiro bloco deve comecar no offset 0")

    def frame_at(self, i: int) -> bytes:
        """Mesma logica de CsoFileReader::ReadChunk."""
        e0, e1 = self.index[i], self.index[i + 1]
        compressed = (e0 & 0x80000000) == 0
        pos = (e0 & 0x7FFFFFFF) << self.align
        end = (e1 & 0x7FFFFFFF) << self.align
        self.f.seek(self.data_off + pos)
        raw = self.f.read(end - pos)
        if not compressed:
            return raw
        out = zlib.decompressobj(-15).decompress(raw)
        if len(out) != self.frame:
            raise SystemExit(f"frame {i}: {len(out)} bytes (esperado {self.frame})")
        return out

    def verify(self, log=print) -> str:
        h = hashlib.sha256()
        t0 = time.time()
        for i in range(self.num):
            h.update(self.frame_at(i))
            if i and i % 250000 == 0:
                log(f"  verificando {i*100//self.num}%...")
        log(f"  verificado em {time.time()-t0:.0f}s")
        return h.hexdigest()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("cso")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--frame", type=int, default=FRAME)
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    info = compress_iso(args.iso, args.cso, args.level, frame=args.frame)
    print(info)
    if not args.no_verify:
        print("conferindo round-trip (decodifica o CSO e compara com o ISO)...")
        got = CsoDecoder(args.cso).verify()
        want = sha256_of(args.iso)
        print("iso", want)
        print("cso", got)
        if got != want:
            raise SystemExit("FALHOU: CSO nao reconstroi o ISO")
        print("OK: CSO reconstroi o ISO byte a byte")


if __name__ == "__main__":
    main()
