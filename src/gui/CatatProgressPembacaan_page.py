import flet as ft
from flet_route import Params, Basket

import sys
import shutil

sys.path.append('.')
sys.path.append('./src')

from src.buku.kumpulanBuku import KumpulanBuku
from src.progresBaca.ProgresBaca import ProgresBaca
from src.progresBaca.KumpulanProgresBaca import KumpulanProgresBaca

class CatatProgresPembacaan:
    def __init__(self):
        self.kb = KumpulanBuku()
        self.kpb = KumpulanProgresBaca()
        self.kb.set_db("read_buddy.db")
        self.kpb.set_db("read_buddy.db")
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

    def save_cover(self, idBuku) :
        if (self.file_picker.result != None) :
            shutil.copyfile(self.file_picker.result.files[0].path, f"src/gui/resources/bookCover/cover{idBuku}.{self.file_picker.result.files[0].path[-3:]}")
        else :
            shutil.copyfile("src/gui/resources/bookCover/nullCover.jpg", f"src/gui/resources/bookCover/cover{idBuku}.jpg")

    def catat_progress_pembacaan(self, page: ft.Page, params: Params, basket: Basket):
        self.page = page
        id_buku = int(params.get("id_buku"))
        page.controls.clear() 
        progresBaca = self.kpb.get_progres_baca(id_buku)
        buku = self.kb.get_by_id(id_buku)

        judul_page = ft.Text(value="DETAIL BUKU " + buku.get_judulBuku(), overflow=ft.TextOverflow.ELLIPSIS, width=500, weight=ft.FontWeight.BOLD)
        nama_aplikasi = ft.Text(value="READ BUDDY")

        button_kembali = ft.ElevatedButton(text="Kembali", on_click= lambda _: page.go("/DetailBuku/" + str(id_buku)))

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

        textField_pembacaan = ft.TextField(input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))

        def catat_pembacaan_clicked(e):
            if(textField_pembacaan.value == ""):
                self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh kosong!"))
                self.page.snack_bar.open = True
                self.page.update()
            
            elif(int(textField_pembacaan.value) > buku.get_total_halaman()) :
                self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh lebih besar dari total halaman buku!"))
                self.page.snack_bar.open = True
                self.page.update()

            else:
                progresBaca.setHalamanSementara(int(textField_pembacaan.value))
                self.kpb.update_progres_baca(ProgresBaca(id_buku, progresBaca.getPembacaanKe(), progresBaca.getHalamanSekarang(), progresBaca.getTanggalMulai()))
                self.page.go("/DetailBuku/" + str(id_buku))

        query_row = ft.Container(
            content=ft.Column(
                [
                    ft.Text(value="Masukkan halaman terakhir pada pembacaan kali ini:", weight=105),
                    textField_pembacaan,
                    ft.ElevatedButton(text="Catat Pembacaan", width=200, on_click=catat_pembacaan_clicked)
                ]
            ), padding=ft.Padding(0, 50, 0, 0)
        )

        detail_row = ft.Container(
            content=ft.Column(
                [
                    ft.TextField(
                        value="Jumlah Halaman: " + str(buku.get_total_halaman()),
                        border=ft.InputBorder.NONE,
                        read_only = True,
                        filled=True),
                    ft.TextField(
                        value="Halaman terakhir yang dibaca: " + str(progresBaca.getHalamanSekarang()),
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
                        src = f"img/bookCover/cover{id_buku}.jpg",
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