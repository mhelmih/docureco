import sqlite3
from src.note.note import Note

class NoteCollection:
    _conn = sqlite3.connect('read_buddy.db', check_same_thread=False)
    _cursor = _conn.cursor()


    def set_db(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._cursor = self._conn.cursor()

    def get_note(self, note_id, book_id) -> Note:
        
        query = "SELECT * FROM catatan WHERE id_catatan = ? AND id_buku = ?"
        self._cursor.execute(query, (note_id, book_id))

        data_catatan = self._cursor.fetchone()

        if data_catatan:
            return Note(data_catatan[0], data_catatan[1], data_catatan[2], data_catatan[3])
        
        else:
            return None
        
    
    def insert(self, note : Note):
        
        query = "INSERT INTO catatan (id_catatan, id_buku, halaman_buku, konten_catatan) VALUES (?, ?, ?, ?)"

        data = (self.get_last_note_id(note._bookId), note.get_bookId(), note.get_bookPage(), note.get_noteContent())

        self._cursor.execute(query, data)
        self._conn.commit()

    def get_note_count(self):
        query = "SELECT COUNT(*) FROM catatan"
        self._cursor.execute(query)

        jumlah = self._cursor.fetchone()
        return jumlah[0]
    
    def get_note_count_per_book(self, bookId):
        query = "SELECT COUNT(*) FROM catatan WHERE id_buku = ?"
        self._cursor.execute(query,(bookId,))

        jumlah = self._cursor.fetchone()
        return jumlah[0]
    

    def get_all_notes(self):
        query = "SELECT * FROM catatan"
        self._cursor.execute(query)

        data_catatan = self._cursor.fetchall()

        return list(map(lambda row : Note(row[0], row[1], row[2], row[3]), data_catatan))
    
    def get_all_notes_per_book(self, bookId):
        query = "SELECT * FROM catatan WHERE id_buku = ?"
        self._cursor.execute(query,(bookId,))

        data_catatan = self._cursor.fetchall()

        return list(map(lambda row : Note(row[0], row[1], row[2], row[3]), data_catatan))
    
    def clear_all(self):
        query = "DELETE FROM catatan"
        self._cursor.execute(query)
        self._conn.commit()

    def delete_note(self, noteId, bookId):
        query = "DELETE FROM catatan WHERE id_catatan = ? AND id_buku = ?"
        self._cursor.execute(query, (noteId, bookId)) 
        self._conn.commit()

    def get_last_note_id(self, bookId):
        query = "SELECT id_catatan FROM catatan WHERE id_buku = ? ORDER BY id_catatan DESC LIMIT 1"
        self._cursor.execute(query,(bookId,))
        idCatatan = self._cursor.fetchone()
        return idCatatan[0]+1 if idCatatan else 1
    
    def edit_note_content_and_page(self, bookId, noteId, noteContent, bookPage):
        query = "UPDATE catatan SET konten_catatan = ?, halaman_buku = ? WHERE id_catatan = ? AND id_buku = ?"
        self._cursor.execute(query,(noteContent, bookPage, noteId, bookId))
        self._conn.commit()