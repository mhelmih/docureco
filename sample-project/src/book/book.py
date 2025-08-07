class Book:
    _bookId = 0
    _bookTitle = ""
    _bookStatus = ""
    _totalPages = 0
    _isFavorite = False
    _coverImage = None

    def __init__(self, bookId, bookTitle, bookStatus, totalPages, isFavorite=False, coverImage=None) -> None:
        self._bookId = bookId
        self._bookTitle = bookTitle
        self._bookStatus = bookStatus
        self._totalPages = totalPages
        self._isFavorite = isFavorite
        self._coverImage = coverImage
        

    def get_bookId(self) :
        return self._bookId
    
    def get_bookTitle(self) :
        return self._bookTitle
    
    def get_bookStatus(self) :
        return self._bookStatus
    
    def get_totalPages(self) :
        return self._totalPages
    
    def get_isFavorite(self) :
        return self._isFavorite

    def get_coverImage(self):
        return self._coverImage
    
    def set_bookId(self, bookId) :
        self._bookId = bookId

    def set_bookTitle(self, bookTitle) :
        self._bookTitle = bookTitle

    def set_bookStatus(self, bookStatus) :
        self._bookStatus = bookStatus

    def set_totalPages(self, totalPages) :
        self._totalPages = totalPages

    def set_isFavorite(self, isFavorite) :
        self._isFavorite = isFavorite

    def set_coverImage(self, coverImage):
        self._coverImage = coverImage

    def __eq__(self, value: object) -> bool:

        if (not isinstance(value, Book)) :
            return False
        
        res = self.get_bookTitle() == value.get_bookTitle()
        res = res and self.get_bookStatus() == value.get_bookStatus()
        res = res and self.get_totalPages() == value.get_totalPages()
        res = res and self.get_isFavorite() == value.get_isFavorite()
        res = res and self.get_coverImage() == value.get_coverImage()
        return res
    
    def delete_by_id(self, id) :
        query = "DELETE FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()