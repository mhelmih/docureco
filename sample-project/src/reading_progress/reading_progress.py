import datetime

class ReadingProgress:

    book_id = ""
    start_date = datetime.datetime.now()
    current_page = 0
    reading_session = 0

    def __init__(self, book_id, reading_session, current_page, start_date):
        self.book_id = book_id
        self.start_date = start_date
        self.current_page = current_page
        self.reading_session = reading_session

    def get_bookId(self) -> int:
        return self.book_id
    
    def set_bookId(self, id : int) -> int:
        self.book_id = id
    
    def getStartDate(self) -> datetime:
        return self.start_date
    
    def setStartDate(self, date):
        self.start_date = date

    def getDayCount(self) -> int:
        date_difference = datetime.datetime.now() - self.start_date

        days_difference = date_difference.days
        return days_difference
    
    def setDayCount(self, hari):
        self = hari
    
    def getCurrentPage(self) -> int:
        return self.current_page
    
    def setCurrentPage(self, page):
        self.current_page = page
    
    def getReadingSession(self) -> int:
        return self.reading_session
    
    def setReadingSession(self, readingSession):
        self.reading_session = readingSession
