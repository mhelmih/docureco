import pytest
from src.book.book_collection import *

def test_buku_constructor() :
    buku = Book(1, "hello", "sedang dibaca", 100)
    assert buku.get_idBuku() == 1
    assert buku.get_judulBuku() == "hello"
    assert buku.get_status_buku() == "sedang dibaca"
    assert buku.get_total_halaman() == 100

def test_buku_setter() :
    buku = Book(1, "hello", "sedang dibaca", 100)

    buku.set_idBuku(5)
    assert buku.get_idBuku() == 5

    buku.set_judulBuku("test")
    assert buku.get_judulBuku() == "test"

    buku.set_status_buku("ingin dibaca")
    assert buku.get_status_buku() == "ingin dibaca"

    buku.set_totalHalaman(89)
    assert buku.get_total_halaman() == 89

def test_buku_eq() :
    buku = Book(1, "hello", "sedang dibaca", 100)

    bukuEq = Book(1, "hello", "sedang dibaca", 100)
    assert buku == bukuEq

    bukuNeq = Book(1, "helloman", "sedang dibaca", 100)
    assert buku != bukuNeq

def test_kumpulan_buku_insert_and_count() :
    kb = BookCollection()
    kb.set_db("tests/testing_db.db")
    kb.clear_all()

    assert kb.get_jumlah_buku() == 0

    kb.insert(Book(1, "test", "ingin dibaca", 77))
    assert kb.get_jumlah_buku() == 1

    kb.clear_all()
    assert kb.get_jumlah_buku() == 0

    kb.clear_all()

def test_kumpulan_buku_insert() :
    kb = BookCollection()
    kb.set_db("tests/testing_db.db")

    buku1 = Book(0, "oracle", "ingin dibaca", 55)
    buku2 = Book(0, "oracle2", "sudah dibaca", 77)

    kb.insert(buku1)
    kb.insert(buku2)

    assert kb.get_jumlah_buku() == 2

    bukuEq = Book(0, "oracle2", "sudah dibaca", 77)
    assert bukuEq == kb.get_by_id(buku2.get_idBuku())

    kb.clear_all()

def test_kumpulan_buku_delete() :
    kb = BookCollection()
    kb.set_db("tests/testing_db.db")

    buku1 = Book(0, "oracle", "ingin dibaca", 55)

    kb.insert(buku1)
    kb.insert(Book(0, "oracle2", "sudah dibaca", 77))

    kb.delete_by_id(buku1.get_idBuku())

    assert kb.get_jumlah_buku() == 1
    assert kb.get_by_id(buku1.get_idBuku()) == None

    kb.clear_all()

def test_kumpulan_buku_update() :
    kb = BookCollection()
    kb.set_db("tests/testing_db.db")

    buku1 = Book(0, "oracle", "ingin dibaca", 55)

    kb.insert(buku1)

    buku1.set_judulBuku("New Judul")
    kb.update_buku(buku1)

    assert kb.get_by_id(buku1.get_idBuku()).get_judulBuku() == "New Judul"

    kb.clear_all()