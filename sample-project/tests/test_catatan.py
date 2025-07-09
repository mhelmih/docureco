import pytest
from src.note.note_collection import *


def test_catatan_constructor():
    catatan = Note(1, 1, 1, "hello")
    assert catatan.get_idCatatan() == 1
    assert catatan.get_idBuku() == 1
    assert catatan.get_halamanBuku() == 1
    assert catatan.get_kontenCatatan() == "hello"

def test_catatan_setter():
    catatan = Note(1, 1, 1, "hello")

    catatan.set_idCatatan(5)
    assert catatan.get_idCatatan() == 5

    catatan.set_idBuku(5)
    assert catatan.get_idBuku() == 5

    catatan.set_halamanBuku(5)
    assert catatan.get_halamanBuku() == 5

    catatan.set_kontenCatatan("test")
    assert catatan.get_kontenCatatan() == "test"


def test_kumpulan_catatan_insert():
    kc = NoteCollection()
    kc.set_db("tests/testing_db.db")
    kc.clear_all()
    catatan1 = Note(0, 1, 1, "hello")
    catatan1EQ = Note(0, 1, 1, "hello")
    assert catatan1 == catatan1EQ
    catatan2 = Note(0, 2, 2, "world")

    kc.insert(catatan1)
    kc.insert(catatan2)

    assert kc.get_jumlah_catatan() == 2
    kc.clear_all()


def test_kumpulan_catatan_delete():
    kc = NoteCollection()
    kc.set_db("tests/testing_db.db")

    kc.clear_all()

    catatan1 = Note(1, 1, 1, "hello")

    kc.insert(catatan1)

    kc.insert(Note(1, 2, 2, "world"))

    kc.delete_catatan(1,2)

    assert kc.get_jumlah_catatan() == 1
    assert kc.get_catatan(1,2) == None

    kc.clear_all() 