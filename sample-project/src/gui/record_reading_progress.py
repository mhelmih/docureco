import flet as ft
from flet_route import Params, Basket

import sys
import shutil

sys.path.append('.')
sys.path.append('./src')

from src.book.book_collection import BookCollection
from src.reading_progress.reading_progress import ReadingProgress
from src.reading_progress.reading_progress_collection import ReadingProgressCollection

class RecordReadingProgress:
    def __init__(self):
        self.book_collection = BookCollection()
        self.reading_progress_collection = ReadingProgressCollection()
        self.book_collection.set_db("read_buddy.db")
        self.reading_progress_collection.set_db("read_buddy.db")
        self.file_picker = ft.FilePicker(on_result=self.save_result)

    def save_result(self, e) :
        self.main_container.content.controls[0] = (
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
        self.main_container.update()

    def save_cover(self, book_id) :
        if (self.file_picker.result != None) :
            shutil.copyfile(self.file_picker.result.files[0].path, f"src/gui/resources/bookCover/cover{book_id}.{self.file_picker.result.files[0].path[-3:]}")
        else :
            shutil.copyfile("src/gui/resources/bookCover/nullCover.jpg", f"src/gui/resources/bookCover/cover{book_id}.jpg")

    def record_reading_progress(self, page: ft.Page, params: Params, basket: Basket):
        self.page = page
        book_id = int(params.get("id_buku"))
        page.controls.clear() 
        reading_progress = self.reading_progress_collection.get_reading_progress(book_id)
        book = self.book_collection.get_by_id(book_id)

        page_title = ft.Text(value="DETAIL BUKU " + book.get_bookTitle(), overflow=ft.TextOverflow.ELLIPSIS, width=500, weight=ft.FontWeight.BOLD)
        app_name = ft.Text(value="READ BUDDY")

        back_button = ft.ElevatedButton(text="Kembali", on_click= lambda _: page.go("/DetailBuku/" + str(book_id)))

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

        reading_field = ft.TextField(input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))

        def record_reading_clicked(e):
            if(reading_field.value == ""):
                self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh kosong!"))
                self.page.snack_bar.open = True
                self.page.update()
            
            elif(int(reading_field.value) > book.get_totalPages()) :
                self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh lebih besar dari total halaman buku!"))
                self.page.snack_bar.open = True
                self.page.update()

            else:
                reading_progress.setCurrentPage(int(reading_field.value))
                self.reading_progress_collection.update_reading_progress(ReadingProgress(book_id, reading_progress.getReadingSession(), reading_progress.getCurrentPage(), reading_progress.getStartDate()))
                self.page.go("/DetailBuku/" + str(book_id))

        query_row = ft.Container(
            content=ft.Column(
                [
                    ft.Text(value="Masukkan halaman terakhir pada pembacaan kali ini:", weight=105),
                    reading_field,
                    ft.ElevatedButton(text="Catat Pembacaan", width=200, on_click=record_reading_clicked)
                ]
            ), padding=ft.Padding(0, 50, 0, 0)
        )

        detail_row = ft.Container(
            content=ft.Column(
                [
                    ft.TextField(
                        value="Jumlah Halaman: " + str(book.get_totalPages()),
                        border=ft.InputBorder.NONE,
                        read_only = True,
                        filled=True),
                    ft.TextField(
                        value="Halaman terakhir yang dibaca: " + str(reading_progress.getCurrentPage()),
                        read_only = True,
                        border=ft.InputBorder.NONE,
                        filled=True),
                    query_row
                ],
            ),
            padding=ft.Padding(50,0,50,0),
            expand=True,
        )

        img_column = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            
            controls=[
                ft.Container(
                    margin=40,
                    height=400,
                    width=300,
                    alignment=ft.alignment.center,
                    content=ft.Image(
                        src = f"img/bookCover/cover{book_id}.jpg",
                        height = 400,
                        width = 300,
                        fit=ft.ImageFit.CONTAIN,
                    ),
                )
            ]
        )

        self.main_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(content=img_column, padding=ft.Padding(50, 0, 50, 0)),
                    detail_row,
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                expand=True
            ),
            padding=ft.Padding(0,20,0,70),
            expand=True
        )

        return ft.View(
            "/CatatProgresPembacaan/:id_buku",

            controls=[
                ft.Column(
                [
                    top_row,
                    self.main_container
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                expand=True
                )

            ]
        )