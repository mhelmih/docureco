import flet as ft
import datetime as dt
from flet_route import Params, Basket
import sys
import shutil

sys.path.append('.')
sys.path.append('./src')

from src.buku.buku import Buku
from src.buku.kumpulanBuku import KumpulanBuku
from src.progresBaca.ProgresBaca import ProgresBaca
from src.progresBaca.KumpulanProgresBaca import KumpulanProgresBaca

class Tambah_Buku:
    def __init__(self):
        self.kb = KumpulanBuku()
        self.kb.set_db("read_buddy.db")
        self.kbp = KumpulanProgresBaca()
        self.kbp.set_db("read_buddy.db")
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

    def save_cover(self, idBuku) :
        if (self.file_picker.result != None) :
            shutil.copyfile(self.file_picker.result.files[0].path, f"img/bookCover/cover{idBuku}.{self.file_picker.result.files[0].path[-3:]}")
        else :
            shutil.copyfile("img/bookCover/nullCover.jpg", f"img/bookCover/cover{idBuku}.jpg")


    def submit_clicked(self, e) :
        if (self.judul_field.value == ""):
            self.error_text.value = "Judul buku harus diisi"
        elif (self.halaman_field.value == ""):
            self.error_text.value = "Halaman buku harus diisi"
        else:
            try:
                halamanBuku = int(self.halaman_field.value)
                if (halamanBuku <= 0):
                    self.error_text.value = "Halaman buku harus bilangan positif"
                else:
                    buku = Buku(None, self.judul_field.value, self.status_buku_dropdown.value.lower(), halamanBuku)
                    self.kb.insert(buku)

                    progresBaca = ProgresBaca(buku.get_idBuku(), 0, 0, dt.datetime(1970, 1, 1))

                    if (self.status_buku_dropdown.value.lower() == 'sedang dibaca') :
                        progresBaca.setPembacaanKe(1)
                        progresBaca.setTanggalMulai(dt.datetime.now())

                    self.error_text.value = "Tambah buku berhasil"
                    self.kbp.insert(progresBaca)

                    self.save_cover(buku.get_idBuku())

                    self.page.go("/")
            except:
                self.error_text.value = "Halaman buku haruslah berupa bilangan bulat"
                self.error_text.update()
                return
            
        self.error_text.update()
    
    def display_tambah_buku(self, page: ft.Page, params : Params, basket : Basket):
        # Headers
        self.page = page
        page.controls.clear()
        judul_page = ft.Text(value="TAMBAH BUKU", size=30, weight=15)
        nama_aplikasi = ft.Text(value="READ BUDDY")
        button_kembali = ft.ElevatedButton(text="Kembali", on_click=lambda _: page.go("/"))

        # Buttons
        button_tambah_buku = ft.ElevatedButton(text="Tambah Buku", width=150, on_click=self.submit_clicked)
        button_upload = ft.ElevatedButton(
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
        self.status_buku_dropdown = ft.Dropdown(
            width=500,
            label = "Status Buku",
            hint_text="Status Buku",
            options=[
                ft.dropdown.Option("Sedang Dibaca"),
                ft.dropdown.Option("Ingin Dibaca"),
            ],
            autofocus=True,
        )
        self.status_buku_dropdown.value = "Sedang Dibaca"
        self.judul_field = ft.TextField(hint_text="Judul Buku", width=500)
        self.halaman_field = ft.TextField(hint_text="Jumlah Halaman", width=500)

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
                            nama_aplikasi,
                            judul_page,
                            button_kembali
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
                    self.judul_field,
                    self.halaman_field,
                    self.status_buku_dropdown,
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            ),
            padding=ft.Padding(10,50,50,50),
            expand=True
        )

        main_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(content=button_upload, padding=ft.Padding(0, 0, 40, 0)),
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
                    button_tambah_buku,
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