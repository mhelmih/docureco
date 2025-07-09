import flet as ft
import datetime as dt
from flet_route import Routing, path
from book_detail import BookDetail
from note_display import NoteDisplay
from add_book import AddBook
from record_reading_progress import RecordReadingProgress
from Main_Page import ReadBuddy

import sys

sys.path.append('.')
sys.path.append('./src')

def MainRouter(page: ft.Page):
    
    def display_note_view(page: ft.Page, params, basket):
        book_id = int(params.get("id_buku"))
        note_display = NoteDisplay(book_id, page)

        view = ft.View(
            "/DisplayCatatan/:id_buku",
            controls = note_display.page.controls
        )
        return view
    
    book_detail = BookDetail()
    add_book = AddBook()
    record_reading_progress = RecordReadingProgress()

    app_routes = [
        path(url="/", clear = True, view = ReadBuddy),
        path(url="/DetailBuku/:id_buku", clear = True, view = book_detail.detail_book),
        path(url="/DisplayCatatan/:id_buku", clear = True, view = display_note_view),
        path(url="/TambahBuku/", clear = True, view = add_book.display_add_book),
        path(url="/CatatProgresPembacaan/:id_buku", clear = True, view = record_reading_progress.record_reading_progress)
    ]

    Routing(page=page, app_routes=app_routes)

    page.go(page.route)

ft.app(target=MainRouter)