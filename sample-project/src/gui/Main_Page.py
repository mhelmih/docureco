import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import flet as ft
from flet_route import Params, Basket
from src.book.book import Book
from src.book.book_collection import BookCollection
from src.reading_progress.reading_progress_collection import ReadingProgressCollection

class BookDisplay(ft.UserControl):
    def __init__(self, book : Book, book_delete, book_status_change, book_favorite_change):
        super().__init__()
        self.book = book
        self.book_status_change = book_status_change
        self.book_delete = book_delete
        self.book_favorite_change = book_favorite_change

    def build(self):

        self.title_display = ft.Row(
            controls=[ft.Text(
                self.book.get_bookTitle(), weight=ft.FontWeight.BOLD
            )]
        )

        self.display_view = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(str(self.book.get_totalPages()) + " halaman"),
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(
                            icon=ft.icons.FAVORITE if self.book.get_isFavorite() else ft.icons.FAVORITE_BORDER,
                            icon_color=ft.colors.RED if self.book.get_isFavorite() else ft.colors.GREY,
                            tooltip="Favorit",
                            on_click=self.favorite_clicked,
                        ),
                        ft.IconButton(
                            icon=ft.icons.ARROW_DROP_DOWN_OUTLINED,
                            on_click=self.detail_clicked,
                        ),
                    ],
                ),
            ],
        )

        self.detail_view_1 = ft.Row(
            visible=False,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(str(self.book.get_totalPages()) + " halaman"),
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(
                            icon=ft.icons.FAVORITE if self.book.get_isFavorite() else ft.icons.FAVORITE_BORDER,
                            icon_color=ft.colors.RED if self.book.get_isFavorite() else ft.colors.GREY,
                            tooltip="Favorit",
                            on_click=self.favorite_clicked,
                        ),
                        ft.IconButton(
                            icon=ft.icons.ARROW_DROP_UP_OUTLINED,
                            on_click=self.close_detail_clicked,
                        ),
                        
                    ],
                ),
            ],
        )
        self.detail_view_2 = ft.Row(
            visible=False,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(self.book.get_bookStatus()),
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.TextButton(
                            text="Ubah Detail",
                            on_click=self.status_changed,
                        ),
                        ft.IconButton(
                            ft.icons.DELETE_OUTLINE,
                            tooltip="Delete To-Do",
                            on_click=self.delete_clicked,
                        ),
                    ],
                ),
            ],
        )

        
        return ft.Column(controls=[self.title_display, self.display_view, self.detail_view_1, self.detail_view_2,ft.Divider()])

    def status_changed(self, e):
        # perlu diganti
        self.page.go("/DetailBuku/" + str(self.book.get_bookId()))

    def delete_clicked(self, e):
        self.book_delete(self)

    def favorite_clicked(self, e):
        self.book_favorite_change(self)

    def detail_clicked(self, e):
        self.detail_view_1.visible = True
        self.detail_view_2.visible = True
        self.display_view.visible = False
        self.update()

    def close_detail_clicked(self, e):
        self.detail_view_1.visible = False
        self.detail_view_2.visible = False
        self.display_view.visible = True
        self.update()


class BookCollectionDisplay(ft.UserControl):
    def __init__(self, book_delete, book_status_change, book_favorite_change):
        super().__init__()
        self.book_collection = BookCollection()
        self.book_collection.set_db("read_buddy.db")
        self.book_list = self.book_collection.get_all()
        self.book_delete = book_delete
        self.book_status_change = book_status_change
        self.book_favorite_change = book_favorite_change

    def build_app_icon(self):
        col = ft.Column(
            alignment=ft.alignment.center,
            controls=[
                ft.Container(
                    margin=20,
                    height=400,
                    width=300,
                    alignment=ft.alignment.center,
                    content=ft.Image(
                        src="img/logo_readbuddy.png",
                        width=300,
                        height=300,
                        fit=ft.ImageFit.CONTAIN,
                    ),

                ),
                ft.Container(
                    margin=20,
                    height=50,
                    width=300,
                    alignment=ft.alignment.center,
                    content=ft.Text("Read Buddy", weight=ft.FontWeight.BOLD, size=25, color=ft.colors.WHITE),
                    bgcolor=ft.colors.GREY_700,
                    border_radius=10,
                ),
            ]
        )

        return col

    def build_list(self):
        panel = ft.Column(
            spacing=10,
            height=400,
            width=600,
            scroll=ft.ScrollMode.ALWAYS,
        )

        for i in range(self.book_list.__len__()):
            panel.controls.append(BookDisplay(self.book_list[i], self.book_delete, self.book_status_change, self.book_favorite_change))
        return panel


class ReadBuddy(ft.UserControl):
    def build(self):
        self.new_book = ft.TextButton(
            text="Tambah Buku",
            on_click=self.add_clicked
        )
        self.book_collection_display = BookCollectionDisplay(self.book_delete, self.book_status_change, self.book_favorite_change)
        self.display_icon = self.book_collection_display.build_app_icon()
        self.book_list_display = self.book_collection_display.build_list()
        self.filter = ft.Tabs(
            scrollable=False,
            selected_index=0,
            on_change=self.tabs_changed,
            # label_color=ft.colors.GREEN,
            # indicator_color=ft.colors.BLACK,
            tabs=[ft.Tab(text="Semua"), ft.Tab(text="Sedang dibaca"), ft.Tab(text="Sudah/ingin dibaca"), ft.Tab(text="Favorit")],
        )

        self.items_left = ft.Text("0 buku yang sedang dibaca")

        self.main_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            controls=[
                self.display_icon,
                ft.Column(
                    width=600,
                    controls=[
                        ft.Column(
                            spacing=25,
                            controls=[
                                self.filter,
                                self.book_list_display,
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        self.items_left,
                                        self.new_book,
                                    ],
                                ),
                            ],
                        )
                    ],
                )
            ],
        )

        return self.main_row

    def add_clicked(self, e):
        self.page.go("/TambahBuku/")

    def book_status_change(self, book):
        self.update()

    def book_favorite_change(self, book):
        # Toggle favorite status
        new_favorite_status = not book.book.get_isFavorite()
        book.book.set_isFavorite(new_favorite_status)
        
        # Update in database
        self.book_collection_display.book_collection.update_favorite_status(book.book.get_bookId(), new_favorite_status)
        
        # Update UI
        self.update()

    def book_delete(self, book):
        self.book_list_display.controls.remove(book)
        self.book_collection_display.book_collection.delete_by_id(book.book.get_bookId())
        kumpulan_progresBaca = ReadingProgressCollection()
        kumpulan_progresBaca.delete_by_id(book.book.get_bookId())
        self.update()

    def tabs_changed(self, e):
        self.update()

    def update(self):
        status = self.filter.tabs[self.filter.selected_index].text
        count = 0
        for book in self.book_list_display.controls:
            book.visible = (
                status == "Semua"
                or (status == "Sedang dibaca" and book.book.get_bookStatus() == "sedang dibaca")
                or (status == "Sudah/ingin dibaca" and book.book.get_bookStatus() != "sedang dibaca")
                or (status == "Favorit" and book.book.get_isFavorite())
            )
            if book.book.get_bookStatus() == "sedang dibaca":
                count += 1
        self.items_left.value = f"{count} buku yang sedang dibaca"
        super().update()


def main(page: ft.Page, params: Params, basket: Basket):
    page.title = "Read Buddy"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    page.appbar = ft.AppBar(
        # bgcolor=ft.colors.SURFACE_VARIANT,
        leading=ft.Container(content=ft.Text(value="Read Buddy", weight=ft.FontWeight.BOLD), alignment=ft.alignment.center, margin=10),
        leading_width=120,
        title=ft.Text("Welcome To Read Buddy", weight=ft.FontWeight.BOLD),
        center_title=True
    )
    page.add(ReadBuddy())

    return ft.View(
        "/",
        controls=page.controls
    )