import flet as ft
from flet_route import Params, Basket

import sys
import shutil

sys.path.append('.')
sys.path.append('./src')

from src.book.book import Book
from src.book.book_collection import BookCollection
from src.reading_progress.reading_progress import ReadingProgress
from src.reading_progress.reading_progress_collection import ReadingProgressCollection
from src.note.note_collection import NoteCollection
from src.note.export_note import export_to_markdown

def to_capitalized_first_word(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]

class BookDetail:

    def __init__(self):
        self.book_collection = BookCollection()
        self.reading_progress_collection = ReadingProgressCollection()
        self.note_collection = NoteCollection()
        self.book_collection.set_db("read_buddy.db")
        self.reading_progress_collection.set_db("read_buddy.db")
        self.note_collection.set_db("read_buddy.db")
        self.file_picker = ft.FilePicker(on_result=self.save_result)
        self.has_upload_cover = False


    def save_result(self, e) :
        new_image_column = ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                
                controls=[
                    ft.Container(
                        alignment=ft.alignment.center,
                        content=ft.Image(
                            src = self.file_picker.result.files[0].path,
                            height = 400,
                            width = 300,
                            fit=ft.ImageFit.CONTAIN,
                        )
                    ),
                    ft.Container(
                        alignment=ft.alignment.center,
                        width = 300,
                        content=self.button_upload
                    )
                ]
        )
        self.main_container.content.controls[0] = ft.Container(content=new_image_column, padding=ft.Padding(50, 0, 50, 0))
        self.main_container.update()

    def save_cover(self, book_id) :
        if (self.file_picker.result != None) :
            shutil.copyfile(self.file_picker.result.files[0].path, f"img/bookCover/cover{book_id}.{self.file_picker.result.files[0].path[-3:]}")
        else :
            shutil.copyfile("img/bookCover/nullCover.jpg", f"img/bookCover/cover{book_id}.jpg")

    def detail_book(self, page: ft.Page, params: Params, basket: Basket):
        self.page = page
        self.page.controls.clear() 
        self.book_id = int(params.get("id_buku"))
        reading_progress = self.reading_progress_collection.get_reading_progress(self.book_id)
        book = self.book_collection.get_by_id(self.book_id)

        page_title = ft.Text(value="DETAIL BUKU " + book.get_bookTitle(), overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.BOLD, width=500)

        app_name = ft.Text(value="READ BUDDY")

        def go_to_home(e):
            self.page.go("/")

        back_button = ft.ElevatedButton(text="Kembali", on_click= go_to_home)

        book_title_field = ft.TextField(value=book.get_bookTitle().upper(), width=500)
        total_pages_field = ft.TextField(value=book.get_totalPages(), input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))
        book_status_field = ft.Dropdown(
            width=700,
            options=[
                ft.dropdown.Option("Sudah Dibaca"),
                ft.dropdown.Option("Ingin Dibaca"),
                ft.dropdown.Option("Sedang Dibaca"),
            ],
            hint_text=to_capitalized_first_word(book.get_bookStatus())
        )
        book_status_field.value = book.get_bookStatus()
        initial_book_status = book.get_bookStatus()
        current_page_field = ft.TextField(value=reading_progress.getCurrentPage(),
                                        input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""),
                                        read_only=True)
        detail_content = (
            f"Kamu mulai membaca buku pada tanggal {reading_progress.getStartDate()}\n"
            f"Sudah {reading_progress.getDayCount()} hari sejak kamu memulai pembacaan\n"
            f"Sekarang adalah pembacaan yang ke-{reading_progress.getReadingSession()}"
        )
        
        detail_field = ft.TextField(value=detail_content, read_only=True, multiline=True)


        def update_data(e):
            if (int(current_page_field.value) > int(total_pages_field.value)):
                snack_bar = ft.SnackBar(
                    content=ft.Text("Halaman sekarang tidak boleh melebihi halaman total!"),
                )
                self.page.snack_bar = snack_bar
                snack_bar.open = True
                self.page.update()
            else :
                if ((initial_book_status == "sudah dibaca" and book_status_field.value == "Sedang Dibaca") or (initial_book_status == "ingin dibaca" and book_status_field.value == "Sedang Dibaca")):
                    temp_reading_session = reading_progress.getReadingSession()
                    reading_progress.setReadingSession(temp_reading_session + 1)
                self.reading_progress_collection.update_reading_progress(ReadingProgress(self.book_id, reading_progress.getReadingSession(), int(current_page_field.value), reading_progress.getStartDate()))
                self.book_collection.update_book(Book(self.book_id, book_title_field.value, book_status_field.value.lower(), int(total_pages_field.value), book.get_isFavorite()))
                self.page.go("/")

        def delete_book(e):
            self.book_collection.delete_by_id(self.book_id)
            self.reading_progress_collection.delete_by_id(self.book_id)
            self.page.go("/")

        view_notes_button = ft.ElevatedButton(text="Lihat Catatan", width=150, on_click= lambda _: self.page.go("/DisplayCatatan/" + str(self.book_id)))
        record_progress_button = ft.ElevatedButton(text="Catat Progres Pembacaan", on_click= lambda _: self.page.go("/CatatProgresPembacaan/" + str(self.book_id)))
        update_button = ft.ElevatedButton(text="Update", width=150, on_click=update_data)
        delete_book_button = ft.ElevatedButton(text="Hapus Buku", on_click=delete_book)
        
        def export_action(e):
            """
            Fetches all notes for the current book and exports them to a markdown file.
            """
            notes = self.note_collection.get_all_notes_by_book_id(self.book_id)
            if not notes:
                snack_bar = ft.SnackBar(content=ft.Text("Tidak ada catatan untuk diekspor!"))
                self.page.snack_bar = snack_bar
                snack_bar.open = True
                self.page.update()
                return

            # Format all notes into a single string
            full_note_content = ""
            for note in notes:
                full_note_content += f"## Catatan pada Halaman {note.get_pageNumber()}\n"
                full_note_content += f"_{note.get_creationDate()}_\n\n"
                full_note_content += f"{note.get_content()}\n\n---\n\n"
            
            # Get book title for the filename
            book = self.book_collection.get_by_id(self.book_id)
            export_to_markdown(full_note_content, book.get_bookTitle())

        export_notes_button = ft.ElevatedButton(text="Ekspor Catatan", width=150, on_click=export_action)

        def toggle_favorite(e):
            new_favorite_status = not book.get_isFavorite()
            book.set_isFavorite(new_favorite_status)
            self.book_collection.update_favorite_status(self.book_id, new_favorite_status)
            
            # Update button appearance
            favorite_button.icon = ft.icons.FAVORITE if new_favorite_status else ft.icons.FAVORITE_BORDER
            favorite_button.icon_color = ft.colors.RED if new_favorite_status else ft.colors.GREY
            favorite_button.text = "Hapus dari Favorit" if new_favorite_status else "Tambah ke Favorit"
            self.page.update()
        
        favorite_button = ft.ElevatedButton(
            text="Hapus dari Favorit" if book.get_isFavorite() else "Tambah ke Favorit",
            icon=ft.icons.FAVORITE if book.get_isFavorite() else ft.icons.FAVORITE_BORDER,
            icon_color=ft.colors.RED if book.get_isFavorite() else ft.colors.GREY,
            on_click=toggle_favorite
        )

        self.top_row = ft.Container(
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

        detail_row = ft.Container(
            content=ft.Column(
                [
                    ft.Text(value="Judul Buku", weight=30),
                    ft.Row(
                        [
                            book_title_field,
                            delete_book_button
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(value="Total Halaman", weight=30),
                    total_pages_field,
                    ft.Text(value="Status Buku", weight=30),
                    book_status_field,
                    ft.Text(value="Halaman Sekarang", weight=30),
                    current_page_field,
                    ft.Text(value="Detail", weight=30),
                    detail_field,
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            ),
            padding=ft.Padding(10,10,70,50),
            expand=True
        )

        self.button_upload = ft.ElevatedButton(
            "Click to upload file",
            on_click=lambda _: self.file_picker.pick_files(allowed_extensions = ["jpg", "png"]),
        )

        self.img_column = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            
            controls=[
                ft.Container(
                    alignment=ft.alignment.center,
                    content=ft.Image(
                        src = f"img/bookCover/cover{self.book_id}.jpg",
                        height = 400,
                        width = 300,
                        fit=ft.ImageFit.CONTAIN,
                    )
                ),
                ft.Container(
                    alignment=ft.alignment.center,
                    width = 300,
                    content=self.button_upload
                )
            ]
        )

        self.main_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(content=self.img_column, padding=ft.Padding(50, 0, 50, 0)),
                    detail_row
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                expand=True
            ),
            padding=ft.Padding(0,20,0,50),
            expand=True
        )

        self.bottom_row = ft.Container(
            content=ft.Row(
                [
                    view_notes_button,
                    export_notes_button,
                    record_progress_button,
                    update_button,
                    favorite_button
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.END
            ),
            padding=ft.Padding(10, 10, 10, 30)
        )

        # File Upload
        self.page.overlay.append(self.file_picker)
        self.page.update()

        return ft.View(
            "/DetailBuku/:id_buku",

            controls=[
                ft.Column(
                [
                    self.top_row,
                    self.main_container,
                    self.bottom_row
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                expand=True
                )

            ]
        )
