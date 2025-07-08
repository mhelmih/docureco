import flet as ft
from flet_route import Params, Basket

import sys
import shutil

sys.path.append('.')
sys.path.append('./src')

from src.buku.buku import Buku
from src.buku.kumpulanBuku import KumpulanBuku
from src.progresBaca.ProgresBaca import ProgresBaca
from src.progresBaca.KumpulanProgresBaca import KumpulanProgresBaca

def to_capitalized_first_word(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]

class DetailBuku:

    def __init__(self):
        self.kb = KumpulanBuku()
        self.kpb = KumpulanProgresBaca()
        self.kb.set_db("read_buddy.db")
        self.kpb.set_db("read_buddy.db")
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

    def save_cover(self, idBuku) :
        if (self.file_picker.result != None) :
            shutil.copyfile(self.file_picker.result.files[0].path, f"img/bookCover/cover{idBuku}.{self.file_picker.result.files[0].path[-3:]}")
        else :
            shutil.copyfile("img/bookCover/nullCover.jpg", f"img/bookCover/cover{idBuku}.jpg")

    def detail_buku(self, page: ft.Page, params: Params, basket: Basket):
        self.page = page
        self.page.controls.clear() 
        self.id_buku = int(params.get("id_buku"))
        progresBaca = self.kpb.get_progres_baca(self.id_buku)
        buku = self.kb.get_by_id(self.id_buku)

        judul_page = ft.Text(value="DETAIL BUKU " + buku.get_judulBuku(), overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.BOLD, width=500)

        nama_aplikasi = ft.Text(value="READ BUDDY")

        def go_to_home(e):
            self.page.go("/")

        button_kembali = ft.ElevatedButton(text="Kembali", on_click= go_to_home)

        judul_buku = ft.TextField(value=buku.get_judulBuku().upper(), width=500)
        total_halaman = ft.TextField(value=buku.get_total_halaman(), input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))
        status_buku = ft.Dropdown(
            width=700,
            options=[
                ft.dropdown.Option("Sudah Dibaca"),
                ft.dropdown.Option("Ingin Dibaca"),
                ft.dropdown.Option("Sedang Dibaca"),
            ],
            hint_text=to_capitalized_first_word(buku.get_status_buku())
        )
        status_buku.value = buku.get_status_buku()
        initial_status_buku = buku.get_status_buku()
        halaman_sekarang = ft.TextField(value=progresBaca.getHalamanSekarang(),
                                        input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""),
                                        read_only=True)
        detail_content = (
            f"Kamu mulai membaca buku pada tanggal {progresBaca.getTanggalMulai()}\n"
            f"Sudah {progresBaca.getPenghitungHari()} hari sejak kamu memulai pembacaan\n"
            f"Sekarang adalah pembacaan yang ke-{progresBaca.getPembacaanKe()}"
        )
        
        detail = ft.TextField(value=detail_content, read_only=True, multiline=True)


        def update_data(e):
            if (int(halaman_sekarang.value) > int(total_halaman.value)):
                snack_bar = ft.SnackBar(
                    content=ft.Text("Halaman sekarang tidak boleh melebihi halaman total!"),
                )
                self.page.snack_bar = snack_bar
                snack_bar.open = True
                self.page.update()
            else :
                if ((initial_status_buku == "sudah dibaca" and status_buku.value == "Sedang Dibaca") or (initial_status_buku == "ingin dibaca" and status_buku.value == "Sedang Dibaca")):
                    temp_pembacaanKe = progresBaca.getPembacaanKe()
                    progresBaca.setPembacaanKe(temp_pembacaanKe + 1)
                self.kpb.update_progres_baca(ProgresBaca(self.id_buku, progresBaca.getPembacaanKe(), int(halaman_sekarang.value), progresBaca.getTanggalMulai()))
                self.kb.update_buku(Buku(self.id_buku, judul_buku.value, status_buku.value.lower(), int(total_halaman.value)))
                self.page.go("/")

        def hapus_buku(e):
            self.kb.delete_by_id(self.id_buku)
            self.kpb.delete_by_id(self.id_buku)
            self.page.go("/")

        button_lihatCatatan = ft.ElevatedButton(text="Lihat Catatan", width=150, on_click= lambda _: self.page.go("/DisplayCatatan/" + str(self.id_buku)))
        button_catatProgesPembacaan = ft.ElevatedButton(text="Catat Progres Pembacaan", on_click= lambda _: self.page.go("/CatatProgresPembacaan/" + str(self.id_buku)))
        button_update = ft.ElevatedButton(text="Update", width=150, on_click=update_data)
        button_hapusBuku = ft.ElevatedButton(text="Hapus Buku", on_click=hapus_buku)

        self.top_row = ft.Container(
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

        detail_row = ft.Container(
            content=ft.Column(
                [
                    ft.Text(value="Judul Buku", weight=30),
                    ft.Row(
                        [
                            judul_buku,
                            button_hapusBuku
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(value="Total Halaman", weight=30),
                    total_halaman,
                    ft.Text(value="Status Buku", weight=30),
                    status_buku,
                    ft.Text(value="Halaman Sekarang", weight=30),
                    halaman_sekarang,
                    ft.Text(value="Detail", weight=30),
                    detail,
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
                        src = f"img/bookCover/cover{self.id_buku}.jpg",
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
                    button_lihatCatatan,
                    button_catatProgesPembacaan,
                    button_update
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
