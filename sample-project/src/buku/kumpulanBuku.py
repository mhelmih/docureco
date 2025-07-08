import sqlite3
from src.buku.buku import Buku

class KumpulanBuku:

    _conn = sqlite3.connect('read_buddy.db', check_same_thread=False)
    _cursor = _conn.cursor()

    def set_db(self, db_path) :
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def get_by_id(self, id_buku) -> Buku :

        query = "SELECT * FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (id_buku,))

        data_buku = self._cursor.fetchone()

        if data_buku:
            return Buku(data_buku[0], data_buku[1], data_buku[2], data_buku[3])
        else :
            return None
        
    def insert(self, buku : Buku) :

        query = "INSERT INTO buku (judul_buku, status_buku, total_halaman) VALUES (?, ?, ?)"

        data = (buku.get_judulBuku(), buku.get_status_buku(), buku.get_total_halaman())

        self._cursor.execute(query, data)

        query = "SELECT LAST_INSERT_ROWID()"
        self._cursor.execute(query)

        buku.set_idBuku(self._cursor.fetchone()[0])

        self._conn.commit()

    def update_buku(self, buku : Buku) :

        query = "UPDATE buku SET judul_buku = ?, status_buku = ?, total_halaman = ? WHERE id_buku = ?"

        data = (buku.get_judulBuku(), buku.get_status_buku(), buku.get_total_halaman(), buku.get_idBuku())

        self._cursor.execute(query, data)
        self._conn.commit()

    def get_jumlah_buku(self) :
        query = "SELECT COUNT(*) FROM buku"
        self._cursor.execute(query)

        jumlah = self._cursor.fetchone()
        return jumlah[0]

    def get_all(self) :
        query = "SELECT * FROM buku"
        self._cursor.execute(query)

        data_buku = self._cursor.fetchall()

        return list(map(lambda row : Buku(row[0], row[1], row[2], row[3]), data_buku))
    
    def clear_all(self) :
        query = "DELETE FROM buku"
        self._cursor.execute(query)
        self._conn.commit()

    def delete_by_id(self, id) :
        query = "DELETE FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()