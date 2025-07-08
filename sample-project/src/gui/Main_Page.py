import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import flet as ft
from flet_route import Params, Basket
from src.buku.buku import Buku
from src.buku.kumpulanBuku import KumpulanBuku
from src.progresBaca.KumpulanProgresBaca import KumpulanProgresBaca


class DisplayBuku(ft.UserControl):
    def __init__(self, buku : Buku, buku_delete, buku_status_change):
        super().__init__()
        self.buku = buku
        self.buku_status_change = buku_status_change
        self.buku_delete = buku_delete

    def build(self):

        self.display_judul = ft.Row(
            controls=[ft.Text(
                self.buku.get_judulBuku(), weight=ft.FontWeight.BOLD
            )]
        )

        self.display_view = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(str(self.buku.get_total_halaman()) + " halaman"),
                ft.Row(
                    spacing=0,
                    controls=[
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
                ft.Text(str(self.buku.get_total_halaman()) + " halaman"),
                ft.Row(
                    spacing=0,
                    controls=[
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
                ft.Text(self.buku.get_status_buku()),
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

        
        return ft.Column(controls=[self.display_judul, self.display_view, self.detail_view_1, self.detail_view_2,ft.Divider()])

    def status_changed(self, e):
        # perlu diganti
        self.page.go("/DetailBuku/" + str(self.buku.get_idBuku()))

    def delete_clicked(self, e):
        self.buku_delete(self)

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


class DisplayKumpulanBuku(ft.UserControl):
    def __init__(self, buku_delete, buku_status_change):
        super().__init__()
        self.kb = KumpulanBuku()
        self.kb.set_db("read_buddy.db")
        self.list_buku = self.kb.get_all()
        self.buku_delete = buku_delete
        self.buku_status_change = buku_status_change

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

        for i in range(self.list_buku.__len__()):
            panel.controls.append(DisplayBuku(self.list_buku[i], self.buku_delete, self.buku_status_change))
        return panel


class ReadBuddy(ft.UserControl):
    def build(self):
        self.new_buku = ft.TextButton(
            text="Tambah Buku",
            on_click=self.add_clicked
        )
        self.display_kumpulan_buku = DisplayKumpulanBuku(self.buku_delete, self.buku_status_change)
        self.display_icon = self.display_kumpulan_buku.build_app_icon()
        self.display_list_buku = self.display_kumpulan_buku.build_list()
        self.filter = ft.Tabs(
            scrollable=False,
            selected_index=0,
            on_change=self.tabs_changed,
            # label_color=ft.colors.GREEN,
            # indicator_color=ft.colors.BLACK,
            tabs=[ft.Tab(text="Semua"), ft.Tab(text="Sedang dibaca"), ft.Tab(text="Sudah/ingin dibaca")],
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
                                self.display_list_buku,
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        self.items_left,
                                        self.new_buku,
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ]
        )

        return ft.Container(
            margin=-10,
            padding=20,
            width="100%",
            height=1000,
            # bgcolor=ft.colors.YELLOW_100,
            content=self.main_row
        )

    def add_clicked(self, e):
        self.page.go("/TambahBuku/")

    def buku_status_change(self, buku):
        self.update()

    def buku_delete(self, buku):
        self.display_list_buku.controls.remove(buku)
        self.display_kumpulan_buku.kb.delete_by_id(buku.buku.get_idBuku())
        kumpulan_progresBaca = KumpulanProgresBaca()
        kumpulan_progresBaca.delete_by_id(buku.buku.get_idBuku())
        self.update()

    def tabs_changed(self, e):
        self.update()

    def update(self):
        status = self.filter.tabs[self.filter.selected_index].text
        count = 0
        for buku in self.display_list_buku.controls:
            buku.visible = (
                status == "Semua"
                or (status == "Sedang dibaca" and buku.buku.get_status_buku() == "sedang dibaca")
                or (status == "Sudah/ingin dibaca" and buku.buku.get_status_buku() != "sedang dibaca")
            )
            if buku.buku.get_status_buku() == "sedang dibaca":
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