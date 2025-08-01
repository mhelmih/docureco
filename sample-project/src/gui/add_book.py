import flet as ft
import datetime as dt
from flet_route import Params, Basket
import sys
import shutil

sys.path.append('.')
sys.path.append('./src')

from src.book.book import Book
from src.book.book_collection import BookCollection
from src.reading_progress.reading_progress import ReadingProgress
from src.reading_progress.reading_progress_collection import ReadingProgressCollection

class AddBook:
    def __init__(self):
        self.book_collection = BookCollection()
        self.book_collection.set_db("read_buddy.db")
        self.reading_progress_collection = ReadingProgressCollection()
        self.reading_progress_collection.set_db("read_buddy.db")
        self.file_picker = ft.FilePicker(on_result=self.save_result)
        self.has_upload_cover = False

    def save_result(self, e) :
        self.thePage.controls[1].content.controls[0] = (
            ft.IconButton(content=ft.Image(
                src=self.file_picker.result.files[0].path,
                width=300,
                height=500,
                fit=ft.ImageFit,
                repeat=ft.ImageRepeat.NO_REPEAT,
                border_radius=ft.border_radius.all(10),
            ),
            width=300, 
            height=500,
            on_click=lambda _: self.file_picker.pick_files(allowed_extensions = ["jpg", "png"])
            )
        )
        self.thePage.update()

    def save_cover(self, bookId) :
        if (self.file_picker.result != None) :
            shutil.copyfile(self.file_picker.result.files[0].path, f"img/bookCover/cover{bookId}.{self.file_picker.result.files[0].path[-3:]}")
        else :
            shutil.copyfile("img/bookCover/nullCover.jpg", f"img/bookCover/cover{bookId}.jpg")


    def submit_clicked(self, e) :
        if (self.book_title_field.value == ""):
            self.error_text.value = "Judul buku harus diisi"
        elif (self.page_count_field.value == ""):
            self.error_text.value = "Halaman buku harus diisi"
        else:
            try:
                page_count = int(self.page_count_field.value)
                if (page_count <= 0):
                    self.error_text.value = "Halaman buku harus bilangan positif"
                else:
                    book = Book(None, self.book_title_field.value, self.book_status_dropdown.value.lower(), page_count, False)
                    self.book_collection.insert(book)

                    reading_progress = ReadingProgress(book.get_bookId(), 0, 0, dt.datetime(1970, 1, 1))

                    if (self.book_status_dropdown.value.lower() == 'sedang dibaca') :
                        reading_progress.setReadingSession(1)
                        reading_progress.setStartDate(dt.datetime.now())

                    self.error_text.value = "Tambah buku berhasil"
                    self.reading_progress_collection.insert(reading_progress)

                    self.save_cover(book.get_bookId())

                    self.page.go("/")
            except:
                self.error_text.value = "Halaman buku haruslah berupa bilangan bulat"
                self.error_text.update()
                return
            
        self.error_text.update()
    
    def display_add_book(self, page: ft.Page, params : Params, basket : Basket):
        # Headers
        self.page = page
        page.controls.clear()
        page_title = ft.Text(value="TAMBAH BUKU", size=30, weight=15)
        app_name = ft.Text(value="READ BUDDY")
        back_button = ft.ElevatedButton(text="Kembali", on_click=lambda _: page.go("/"))

        # Buttons
        add_book_button = ft.ElevatedButton(text="Tambah Buku", width=150, on_click=self.submit_clicked)
        upload_button = ft.ElevatedButton(
            "Click to upload file",
            width=300,
            height=500,
            style=ft.ButtonStyle(
                shape= ft.ContinuousRectangleBorder(
                    radius=100
                ),
            ),
            on_click=lambda _: self.file_picker.pick_files(allowed_extensions = ["jpg", "png"]),
        )

        # Fields
        self.book_status_dropdown = ft.Dropdown(
            width=500,
            label = "Status Buku",
            hint_text="Status Buku",
            options=[
                ft.dropdown.Option("Sedang Dibaca"),
                ft.dropdown.Option("Ingin Dibaca"),
            ],
            autofocus=True,
        )
        self.book_status_dropdown.value = "Sedang Dibaca"
        self.book_title_field = ft.TextField(hint_text="Judul Buku", width=500)
        self.page_count_field = ft.TextField(hint_text="Jumlah Halaman", width=500)

        # Text
        self.error_text = ft.Text(value="")

        # File Upload
        self.page.overlay.append(self.file_picker)
        self.page.update()


        top_row = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            app_name,
                            page_title,
                            back_button
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    ft.Divider()
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=ft.Padding(10, 10, 10, 10)
        )

        self.detail_row = ft.Container(
            content=ft.Column(
                [
                    self.book_title_field,
                    self.page_count_field,
                    self.book_status_dropdown,
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            ),
            padding=ft.Padding(10,50,50,50),
            expand=True
        )

        main_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(content=upload_button, padding=ft.Padding(0, 0, 40, 0)),
                    ft.Container(content=self.detail_row, padding=ft.Padding(40, 0, 0, 0)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                expand=True
            ),
            padding=ft.Padding(70,20,40,70),
            expand=True
        )

        bottom_row = ft.Container(
            content=ft.Row(
                [
                    self.error_text,
                    add_book_button,
                ],
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.END
            ),
            padding=ft.Padding(10, 10, 10, 30)
        )

        self.thePage =ft.Column(
            [
                top_row,
                main_container,
                bottom_row
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            expand=True
            )

        return ft.View(
            "/TambahBuku/",

            controls=[
                    self.thePage
            ]
        )