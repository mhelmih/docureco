class Note:

    _noteId = 0
    _bookId = 0
    _bookPage = 0
    _noteContent = ""


    def __init__(self, noteId, bookId, bookPage, noteContent):
        self._noteId = noteId
        self._bookId = bookId
        self._bookPage = bookPage
        self._noteContent = noteContent

    def get_noteId(self):
        return self._noteId
    
    def get_bookId(self):
        return self._bookId
    
    def get_bookPage(self):
        return self._bookPage
    
    def get_noteContent(self):
        return self._noteContent
    
    def set_noteId(self, noteId):
        self._noteId = noteId

    def set_bookId(self, bookId):
        self._bookId = bookId

    def set_bookPage(self, bookPage):
        self._bookPage = bookPage

    def set_noteContent(self, noteContent):
        self._noteContent = noteContent

    def __eq__(self, other) -> bool:
        if not isinstance(other, Note) :
            return False

        return self.get_noteId() == other.get_noteId() and self.get_bookId() == other.get_bookId() and self.get_bookPage() == other.get_bookPage() and self.get_noteContent() == other.get_noteContent()