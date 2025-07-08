import sqlite3
import datetime as dt
from src.progresBaca.ProgresBaca import ProgresBaca

class KumpulanProgresBaca:
    _conn = sqlite3.connect('read_buddy.db', check_same_thread=False)
    _cursor = _conn.cursor()
    
    def set_db(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def get_progres_baca(self, id_buku) -> ProgresBaca:

        query = "SELECT * FROM progres_baca WHERE id_buku = ?"
        self._cursor.execute(query, (id_buku,))

        data_progresBaca = self._cursor.fetchone()

        if data_progresBaca:
            return ProgresBaca(data_progresBaca[0], data_progresBaca[1], data_progresBaca[2], dt.datetime.strptime(data_progresBaca[3], "%Y-%m-%d %H:%M:%S.%f"))
        else:
            return None
    
    def insert(self, progresBaca : ProgresBaca) :

        query = "INSERT INTO progres_baca (id_buku, pembacaan_ke, halaman_terakhir, tanggal_mulai) VALUES (?, ?, ?, ?)"

        data = (progresBaca.get_idBuku(), progresBaca.getPembacaanKe(), progresBaca.getHalamanSekarang(), progresBaca.getTanggalMulai())

        self._cursor.execute(query, data)

        query = "SELECT LAST_INSERT_ROWID()"
        self._cursor.execute(query)

        progresBaca.set_idBuku(self._cursor.fetchone()[0])

        self._conn.commit()

    def update_progres_baca(self, progres_baca : ProgresBaca) :

        query = "UPDATE progres_baca SET pembacaan_ke = ?, halaman_terakhir = ?, tanggal_mulai = ? WHERE id_buku = ?"

        data = (progres_baca.getPembacaanKe(), progres_baca.getHalamanSekarang(), progres_baca.getTanggalMulai(), progres_baca.get_idBuku())

        self._cursor.execute(query, data)
        self._conn.commit()


    def get_jumlah_progresBaca(self) :
        query = "SELECT COUNT(*) FROM progres_baca"
        self._cursor.execute(query)

        jumlah = self._cursor.fetchone()
        return jumlah[0]

    def get_all(self) :
        query = "SELECT * FROM progres_baca"
        self._cursor.execute(query)

        data_progresBaca = self._cursor.fetchall()

        return list(map(lambda row : ProgresBaca(row[0], row[1], row[2], row[3]), data_progresBaca))
    
    def clear_all(self) :
        query = "DELETE FROM progres_baca"
        self._cursor.execute(query)
        self._conn.commit()

    def delete_by_id(self, id) :
        query = "DELETE FROM progres_baca WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()
