#!/usr/bin/env python3
"""
Testes do conversor ISO -> CSO e do "o emulador reconhece este disco?".

   python3 -m unittest tools/test_iso_to_cso.py -v

Monta ISOs de PS2 sinteticos (PVD na trilha 16, SYSTEM.CNF, SLES_xxx.xx) e confere:
  - round-trip byte a byte em frames de 2048 e de 32768;
  - as checagens que o CsoFileReader/CsoFileReader.cpp faz (magic, ver, frame,
    offsets ABSOLUTOS, indice terminando no tamanho do arquivo);
  - os testes que o BIOS faz (PVD/CD001/PLAYSTATION + SYSTEM.CNF/BOOT2), que sao
    exatamente o que decide entre "abrir o jogo" e "Inserir um disco...";
  - os defeitos historicos: offsets relativos e frame < 2048 tem de FALHAR.
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import iso_to_cso as tool  # noqa: E402

SECTOR = 2048
PVD_LBA = 16
ROOT_LBA = 20
CNF_LBA = 21
EXE_LBA = 22


def _le32(v):
    return struct.pack("<I", v)


def _be32(v):
    return struct.pack(">I", v)


def _both16(v):
    return struct.pack("<H", v) + struct.pack(">H", v)


def dir_record(name, lba, size, flags=0):
    raw = name.encode("latin-1")
    rec_len = 33 + len(raw)
    if rec_len % 2:
        rec_len += 1
    buf = bytearray(rec_len)
    buf[0] = rec_len
    buf[2:6] = _le32(lba)
    buf[6:10] = _be32(lba)
    buf[10:14] = _le32(size)
    buf[14:18] = _be32(size)
    buf[25] = flags
    buf[28:32] = _both16(1)
    buf[32] = len(raw)
    buf[33:33 + len(raw)] = raw
    return bytes(buf)


def make_iso(path, total_sectors=8192, frame_hint=None, with_system_cnf=True,
             boot2="cdrom0:\\SLES_537.18;1", with_exe=True,
             system_id=b"PLAYSTATION", pvd_id=b"CD001"):
    """ISO9660 minimo com a cara de um DVD de PS2 (o que o BIOS exige)."""
    size = total_sectors * SECTOR
    with open(path, "wb") as f:
        f.truncate(size)
        # area de sistema (setores 0..15): lixo tipico de masterizacao
        f.seek(0)
        f.write(bytes((i * 37 + 11) & 0xFF for i in range(16 * SECTOR)))

        exe = bytes((i * 131 + 7) & 0xFF for i in range(4096)) if with_exe else b""
        cnf = (f"BOOT2 = {boot2}\r\nVER = 1.00\r\nVMODE = PAL\r\n".encode("latin-1")
               if with_system_cnf else b"")

        root = bytearray(SECTOR)
        entries = [dir_record("\x00", ROOT_LBA, SECTOR, 2),
                   dir_record("\x01", ROOT_LBA, SECTOR, 2)]
        if with_system_cnf:
            entries.append(dir_record("SYSTEM.CNF;1", CNF_LBA, len(cnf)))
        if with_exe:
            entries.append(dir_record("SLES_537.18;1", EXE_LBA, len(exe)))
        off = 0
        for e in entries:
            root[off:off + len(e)] = e
            off += len(e)

        pvd = bytearray(SECTOR)
        pvd[0] = 1
        pvd[1:6] = pvd_id
        pvd[6] = 1
        pvd[8:40] = system_id.ljust(32, b" ")
        pvd[40:72] = b"SIMS2_TEST".ljust(32, b" ")
        pvd[80:84] = _le32(total_sectors)
        pvd[84:88] = _be32(total_sectors)
        pvd[120:124] = _both16(1)
        pvd[124:128] = _both16(0)
        pvd[128:130] = struct.pack("<H", SECTOR)
        pvd[130:132] = struct.pack(">H", SECTOR)
        pvd[156:190] = dir_record("\x00", ROOT_LBA, SECTOR, 2)
        pvd[881] = 1

        f.seek(PVD_LBA * SECTOR)
        f.write(pvd)
        f.seek((PVD_LBA + 1) * SECTOR)
        term = bytearray(SECTOR)
        term[0] = 255
        term[1:6] = pvd_id
        f.write(term)

        f.seek(ROOT_LBA * SECTOR)
        f.write(root)
        f.seek(CNF_LBA * SECTOR)
        f.write(cnf)
        if with_exe:
            f.seek(EXE_LBA * SECTOR)
            f.write(exe)

        # dados incompressiveis/preenchimento (exercita bloco cru e comprimido)
        f.seek(64 * SECTOR)
        block = bytes(range(256)) * 8          # comprime bem
        for i in range(64, min(total_sectors, 640)):
            f.seek(i * SECTOR)
            f.write(block)
        f.seek(4096 * SECTOR)
        f.write(os.urandom(48 * SECTOR))
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cso-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.tmp, name)


class TestRoundTrip(Base):
    def _round_trip(self, frame):
        iso = make_iso(self.path("jogo.iso"))
        cso = self.path(f"jogo-{frame}.cso")
        info = tool.compress_iso(iso, cso, level=1, log=lambda *a: None, frame=frame)
        self.assertEqual(info["frames"], os.path.getsize(iso) // frame)

        res = tool.audit_cso(cso, deep=True, log=lambda *a: None)
        self.assertEqual(res["structure"]["align"], 0)
        self.assertEqual(res["sha256"], tool.sha256_of(iso))
        self.assertEqual(res["disc"]["boot2"], "cdrom0:\\SLES_537.18;1")
        self.assertEqual(res["disc"]["exe"], "SLES_537.18")
        self.assertEqual(res["disc"]["vmode"], "PAL")

    def test_frame_2048(self):
        self._round_trip(2048)

    def test_frame_32768(self):
        self._round_trip(32768)

    def test_offsets_sao_absolutos(self):
        iso = make_iso(self.path("jogo.iso"))
        cso = self.path("jogo.cso")
        tool.compress_iso(iso, cso, log=lambda *a: None)
        dec = tool.CsoDecoder(cso)
        self.assertEqual((dec.index[0] & 0x7FFFFFFF) << dec.align, dec.data_off)
        self.assertEqual((dec.index[-1] & 0x7FFFFFFF) << dec.align,
                         os.path.getsize(cso))
        dec.close()


class TestCheckRecusa(Base):
    """Cada defeito historico tem de ser recusado com mensagem util."""

    def setUp(self):
        super().setUp()
        self.iso = make_iso(self.path("jogo.iso"))
        self.cso = self.path("jogo.cso")
        tool.compress_iso(self.iso, self.cso, log=lambda *a: None)

    def _patch(self, offset, data):
        with open(self.cso, "r+b") as f:
            f.seek(offset)
            f.write(data)

    def test_offsets_relativos(self):
        dec = tool.CsoDecoder(self.cso)
        data_off, count = dec.data_off, dec.num + 1
        dec.close()
        with open(self.cso, "r+b") as f:
            f.seek(tool.HEADER_SIZE)
            idx = list(struct.unpack(f"<{count}I", f.read(4 * count)))
            idx = [(v & 0x80000000) | ((v & 0x7FFFFFFF) - data_off) for v in idx]
            f.seek(tool.HEADER_SIZE)
            f.write(struct.pack(f"<{count}I", *idx))
        with self.assertRaises(tool.DiscCheckError) as ctx:
            tool.audit_cso(self.cso, log=lambda *a: None)
        self.assertIn("ABSOLUTOS", str(ctx.exception))

    def test_frame_menor_que_setor(self):
        self._patch(16, struct.pack("<I", 1024))
        with self.assertRaises(tool.DiscCheckError) as ctx:
            tool.audit_cso(self.cso, log=lambda *a: None)
        self.assertIn("frame_size", str(ctx.exception))

    def test_magic_errado(self):
        self._patch(0, b"ISO!")
        with self.assertRaises(tool.DiscCheckError) as ctx:
            tool.audit_cso(self.cso, log=lambda *a: None)
        self.assertIn("CISO", str(ctx.exception))

    def test_cso_truncado(self):
        with open(self.cso, "r+b") as f:
            f.truncate(os.path.getsize(self.cso) - 4096)
        with self.assertRaises(tool.DiscCheckError) as ctx:
            tool.audit_cso(self.cso, log=lambda *a: None)
        self.assertIn("truncado", str(ctx.exception).lower())

    def test_disparar_boot_check_da_cli(self):
        out = subprocess.run([sys.executable, os.path.join(HERE, "iso_to_cso.py"),
                              "--check", self.cso], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("reconhece este disco", out.stdout)


class TestBootCheck(Base):
    def _audit(self, **kwargs):
        iso = make_iso(self.path("jogo.iso"), **kwargs)
        cso = self.path("jogo.cso")
        tool.compress_iso(iso, cso, log=lambda *a: None)
        return tool.audit_cso(cso, deep=False, log=lambda *a: None)

    def test_dvd_ps2_valido(self):
        res = self._audit()
        self.assertEqual(res["disc"]["system_id"], "PLAYSTATION")

    def test_sem_system_cnf(self):
        with self.assertRaises(tool.DiscCheckError) as ctx:
            self._audit(with_system_cnf=False)
        self.assertIn("SYSTEM.CNF", str(ctx.exception))

    def test_boot2_aponta_para_arquivo_inexistente(self):
        with self.assertRaises(tool.DiscCheckError) as ctx:
            self._audit(with_exe=False)
        self.assertIn("BOOT2", str(ctx.exception))

    def test_system_id_que_nao_e_playstation(self):
        with self.assertRaises(tool.DiscCheckError) as ctx:
            self._audit(system_id=b"WIN32")
        self.assertIn("PLAYSTATION", str(ctx.exception))

    def test_pvd_invalido(self):
        with self.assertRaises(tool.DiscCheckError) as ctx:
            self._audit(pvd_id=b"CD002")
        self.assertIn("CD001", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
