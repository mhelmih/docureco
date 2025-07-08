import sqlite3
from src.catatan.Catatan import Catatan


class KumpulanCatatan:
    _conn = sqlite3.connect('read_buddy.db', check_same_thread=False)
    _cursor = _conn.cursor()


    def set_db(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def get_catatan(self, id_catatan, id_buku) -> Catatan:
        
        query = "SELECT * FROM catatan WHERE id_catatan = ? AND id_buku = ?"
        self._cursor.execute(query, (id_catatan, id_buku))

        data_catatan = self._cursor.fetchone()

        if data_catatan:
            return Catatan(data_catatan[0], data_catatan[1], data_catatan[2], data_catatan[3])
        
        else:
            return None
        
    
    def insert(self,catatan : Catatan):
        
        query = "INSERT INTO catatan (id_catatan, id_buku, halaman_buku, konten_catatan) VALUES (?, ?, ?, ?)"

        data = (self.get_last_id_catatan(catatan._idBuku), catatan.get_idBuku(), catatan.get_halamanBuku(), catatan.get_kontenCatatan())

        self._cursor.execute(query, data)
        self._conn.commit()

    def get_jumlah_catatan(self):
        query = "SELECT COUNT(*) FROM catatan"
        self._cursor.execute(query)

        jumlah = self._cursor.fetchone()
        return jumlah[0]
    
    def get_jumlah_catatan_per_buku(self,idBuku):
        query = "SELECT COUNT(*) FROM catatan WHERE id_buku = ?"
        self._cursor.execute(query,(idBuku,))

        jumlah = self._cursor.fetchone()
        return jumlah[0]
    

    def get_all_catatan(self):
        query = "SELECT * FROM catatan"
        self._cursor.execute(query)

        data_catatan = self._cursor.fetchall()

        return list(map(lambda row : Catatan(row[0], row[1], row[2], row[3]), data_catatan))
    
    def get_all_catatan_per_buku(self,idBuku):
        query = "SELECT * FROM catatan WHERE id_buku = ?"
        self._cursor.execute(query,(idBuku,))

        data_catatan = self._cursor.fetchall()

        return list(map(lambda row : Catatan(row[0], row[1], row[2], row[3]), data_catatan))
    
    def clear_all(self):
        query = "DELETE FROM catatan"
        self._cursor.execute(query)
        self._conn.commit()

    def delete_catatan(self,idCatatan,idBuku):
        query = "DELETE FROM catatan WHERE id_catatan = ? AND id_buku = ?"
        self._cursor.execute(query, (idCatatan,idBuku)) 
        self._conn.commit()

    def get_last_id_catatan(self,idBuku):
        query = "SELECT id_catatan FROM catatan WHERE id_buku = ? ORDER BY id_catatan DESC LIMIT 1"
        self._cursor.execute(query,(idBuku,))
        idCatatan = self._cursor.fetchone()
        return idCatatan[0]+1 if idCatatan else 1
    
    def edit_konten_halaman_catatan(self,idBuku,idCatatan,kontenCatatan,halamanCatatan):
        query = "UPDATE catatan SET konten_catatan = ?, halaman_buku = ? WHERE id_catatan = ? AND id_buku = ?"
        self._cursor.execute(query,(kontenCatatan,halamanCatatan,idCatatan,idBuku))
        self._conn.commit()