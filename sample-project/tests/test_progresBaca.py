import pytest
import datetime as dt
from src.progresBaca.KumpulanProgresBaca import *

def test_progreBaca_constructor() :
    progresBaca = ProgresBaca(1, 1, 100, dt.datetime(2024,1,1))
    assert progresBaca.get_idBuku() == 1
    assert progresBaca.getTanggalMulai() == dt.datetime(2024,1,1)
    assert progresBaca.getHalamanSekarang() == 100
    assert progresBaca.getPembacaanKe() == 1

def test_progresBaca_setter() :
    progresBaca = ProgresBaca(1, 1, 100, dt.datetime(2024,1,1))

    progresBaca.set_idBuku(5)
    assert progresBaca.get_idBuku() == 5

    progresBaca.setTanggalMulai(dt.datetime(1,1,1))
    assert progresBaca.getTanggalMulai() == dt.datetime(1,1,1)

    progresBaca.setHalamanSementara(123)
    assert progresBaca.getHalamanSekarang() == 123

    progresBaca.setPembacaanKe(3)
    assert progresBaca.getPembacaanKe() == 3

def test_kumpulan_progresBaca_insert_and_count() :
    kpb = KumpulanProgresBaca()
    kpb.set_db("tests/testing_db.db")
    kpb.clear_all()

    assert kpb.get_jumlah_progresBaca() == 0

    kpb.insert(ProgresBaca(1, 2, 100, dt.datetime(2024,2,2)))
    assert kpb.get_jumlah_progresBaca() == 1

    kpb.clear_all()
    assert kpb.get_jumlah_progresBaca() == 0

    kpb.clear_all()

def test_kumpulan_progresBaca_insert() :
    kpb = KumpulanProgresBaca()
    kpb.set_db("tests/testing_db.db")

    progresBaca1 = ProgresBaca(1, 1, 50, dt.datetime(2024,3,3))
    progresBaca2 = ProgresBaca(2, 3, 70, dt.datetime(2024,4,4))

    kpb.insert(progresBaca1)
    kpb.insert(progresBaca2)

    assert kpb.get_jumlah_progresBaca() == 2

    kpb.clear_all()

def test_kumpulan_progresBaca_delete() :
    kpb = KumpulanProgresBaca()
    kpb.set_db("tests/testing_db.db")

    progresBaca1 = ProgresBaca(1, 1, 50, dt.datetime(2024,3,3))

    kpb.insert(progresBaca1)
    kpb.insert(ProgresBaca(2, 3, 70, dt.datetime(2024,4,4)))

    kpb.delete_by_id(progresBaca1.get_idBuku())

    assert kpb.get_jumlah_progresBaca() == 1
    assert kpb.get_progres_baca(progresBaca1.get_idBuku()) == None

    kpb.clear_all()
