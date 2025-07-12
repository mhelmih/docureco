import sqlite3
from src.book.book import Book

class BookCollection:

    _conn = sqlite3.connect('read_buddy.db', check_same_thread=False)
    _cursor = _conn.cursor()

    def set_db(self, db_path) :
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def get_by_id(self, book_id) -> Book :

        query = "SELECT * FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (book_id,))

        data_buku = self._cursor.fetchone()

        if data_buku:
            return Book(data_buku[0], data_buku[1], data_buku[2], data_buku[3])
        else :
            return None
        
    def insert(self, book : Book) :

        query = "INSERT INTO buku (judul_buku, status_buku, total_halaman) VALUES (?, ?, ?)"

        data = (book.get_bookTitle(), book.get_bookStatus(), book.get_totalPages())

        self._cursor.execute(query, data)

        query = "SELECT LAST_INSERT_ROWID()"
        self._cursor.execute(query)

        book.set_bookId(self._cursor.fetchone()[0])

        self._conn.commit()

    def update_book(self, book : Book) :

        query = "UPDATE buku SET judul_buku = ?, status_buku = ?, total_halaman = ? WHERE id_buku = ?"

        data = (book.get_bookTitle(), book.get_bookStatus(), book.get_totalPages(), book.get_bookId())

        self._cursor.execute(query, data)
        self._conn.commit()

    def get_book_count(self) :
        query = "SELECT COUNT(*) FROM buku"
        self._cursor.execute(query)

        jumlah = self._cursor.fetchone()
        return jumlah[0]

    def get_all(self) :
        query = "SELECT * FROM buku"
        self._cursor.execute(query)

        data_buku = self._cursor.fetchall()

        return list(map(lambda row : Book(row[0], row[1], row[2], row[3]), data_buku))
    
    def clear_all(self) :
        query = "DELETE FROM buku"
        self._cursor.execute(query)
        self._conn.commit()

    def delete_by_id(self, id) :
        query = "DELETE FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()