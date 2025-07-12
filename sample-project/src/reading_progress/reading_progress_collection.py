import sqlite3
import datetime as dt
from src.reading_progress.reading_progress import ReadingProgress

class ReadingProgressCollection:
    _conn = sqlite3.connect('read_buddy.db', check_same_thread=False)
    _cursor = _conn.cursor()
    
    def set_db(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def get_reading_progress(self, book_id) -> ReadingProgress:

        query = "SELECT * FROM progres_baca WHERE id_buku = ?"
        self._cursor.execute(query, (book_id,))

        data_progresBaca = self._cursor.fetchone()

        if data_progresBaca:
            return ReadingProgress(data_progresBaca[0], data_progresBaca[1], data_progresBaca[2], dt.datetime.strptime(data_progresBaca[3], "%Y-%m-%d %H:%M:%S.%f"))
        else:
            return None
    
    def insert(self, readingProgress : ReadingProgress) :

        query = "INSERT INTO progres_baca (id_buku, pembacaan_ke, halaman_terakhir, tanggal_mulai) VALUES (?, ?, ?, ?)"

        data = (readingProgress.get_bookId(), readingProgress.getReadingSession(), readingProgress.getCurrentPage(), readingProgress.getStartDate())

        self._cursor.execute(query, data)

        query = "SELECT LAST_INSERT_ROWID()"
        self._cursor.execute(query)

        readingProgress.set_bookId(self._cursor.fetchone()[0])

        self._conn.commit()

    def update_reading_progress(self, progress : ReadingProgress) :

        query = "UPDATE progres_baca SET pembacaan_ke = ?, halaman_terakhir = ?, tanggal_mulai = ? WHERE id_buku = ?"

        data = (progress.getReadingSession(), progress.getCurrentPage(), progress.getStartDate(), progress.get_bookId())

        self._cursor.execute(query, data)
        self._conn.commit()


    def get_reading_progress_count(self) :
        query = "SELECT COUNT(*) FROM progres_baca"
        self._cursor.execute(query)

        jumlah = self._cursor.fetchone()
        return jumlah[0]

    def get_all(self) :
        query = "SELECT * FROM progres_baca"
        self._cursor.execute(query)

        data_progresBaca = self._cursor.fetchall()

        return list(map(lambda row : ReadingProgress(row[0], row[1], row[2], row[3]), data_progresBaca))
    
    def clear_all(self) :
        query = "DELETE FROM progres_baca"
        self._cursor.execute(query)
        self._conn.commit()

    def delete_by_id(self, id) :
        query = "DELETE FROM progres_baca WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()
