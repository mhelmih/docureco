class Book:
    _bookId = 0
    _bookTitle = ""
    _bookStatus = ""
    _totalPages = 0

    def __init__(self, bookId, bookTitle, bookStatus, totalPages) -> None:
        self._bookId = bookId
        self._bookTitle = bookTitle
        self._bookStatus = bookStatus
        self._totalPages = totalPages
        

    def get_bookId(self) :
        return self._bookId
    
    def get_bookTitle(self) :
        return self._bookTitle
    
    def get_bookStatus(self) :
        return self._bookStatus
    
    def get_totalPages(self) :
        return self._totalPages
    
    def set_bookId(self, bookId) :
        self._bookId = bookId

    def set_bookTitle(self, bookTitle) :
        self._bookTitle = bookTitle

    def set_bookStatus(self, bookStatus) :
        self._bookStatus = bookStatus

    def set_totalPages(self, totalPages) :
        self._totalPages = totalPages

    def __eq__(self, value: object) -> bool:

        if (not isinstance(value, Book)) :
            return False
        
        res = self.get_bookTitle() == value.get_bookTitle()
        res = res and self.get_bookStatus() == value.get_bookStatus()
        res = res and self.get_totalPages() == value.get_totalPages()
        return res
    
    def delete_by_id(self, id) :
        query = "DELETE FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()