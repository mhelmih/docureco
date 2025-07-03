import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import flet as ft
from src.catatan.Catatan import Catatan
from src.catatan.KumpulanCatatan import KumpulanCatatan
from src.buku.kumpulanBuku import KumpulanBuku
from src.buku.buku import Buku
from src.gui.FormUbahCatatan import FormUbahCatatan



class DisplayCatatan():
    def __init__(self, idBuku, page : ft.Page):
        
        self.idBuku = idBuku
        self.page = page
        self.kc = KumpulanCatatan()
        self.kb = KumpulanBuku()
        self.kc.set_db("read_buddy.db")
        self.kb.set_db("read_buddy.db")
        self.listCatatan = self.kc.get_all_catatan_per_buku(idBuku)
        self.judulBuku = (self.kb.get_by_id(idBuku)).get_judulBuku()
        self.totalHalaman = (self.kb.get_by_id(idBuku)).get_total_halaman()

        self.list : ft.Column = self.build_list()
        self.build()
        self.update_and_sort_list()
       

    def build(self):
        # self.page.theme = ft.Theme(color_scheme_seed=ft.colors.WHITE)
        nama_aplikasi = ft.Text(value="READ BUDDY", weight=ft.FontWeight.BOLD)
        judul_page = ft.Text(self.judulBuku, weight=ft.FontWeight.BOLD,overflow=ft.TextOverflow.ELLIPSIS,)

        button_kembali = ft.ElevatedButton(text="Kembali", on_click= lambda _: self.page.go("/DetailBuku/" + str(self.idBuku)))
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

        content_container = ft.Container(
            margin=-10,
            padding=20,
            width="100%",
            height=1000,
            # bgcolor=ft.colors.GREY_100,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[
                    self.build_cover(),
                    ft.Column(
                        controls=[
                            ft.Container(
                                width=800,
                                bgcolor=ft.colors.GREY_500,
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text("List Catatan", weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                                        ft.IconButton(icon=ft.icons.ADD, on_click=lambda e: self.tambah_catatan_pressed()),
                                    ]
                                ),
                                alignment=ft.alignment.center,
    
                                padding=10,
                                # bgcolor=ft.colors.GREY_400,
                                border_radius=10,
                            ),
                            ft.Container(
                                width = 800,
                                content=self.list,
                                border_radius=10,
                            )
                        ]
                    )
                ]
            ),
        )
        
        main_container = ft.Container(
            content=ft.Column(
                controls=[
                    top_row,
                    content_container,
                ]
            )
        )
        self.page.add(main_container)
        # self.page.update()
        

    def build_cover(self):
        col = ft.Column(
            alignment=ft.alignment.center,
            
            controls=[
                ft.Container(
                    margin=40,
                    height=400,
                    width=300,
                    alignment=ft.alignment.center,
                    content=ft.Image(
                        src = f"img/bookCover/cover{self.idBuku}.jpg",
                        height = 400,
                        width = 300,
                        fit=ft.ImageFit.CONTAIN,
                    ),
                    # bgcolor=ft.colors.GREY_800,
                ),
                ft.Container(
                    margin = ft.Margin(40,0,40,40),
                    height=50,
                    width=300,
                    alignment=ft.alignment.center,
                    content=ft.Text(self.judulBuku,overflow=ft.TextOverflow.FADE,text_align=ft.TextAlign.CENTER,size=15,weight=ft.FontWeight.BOLD,color=ft.colors.WHITE),
                    bgcolor=ft.colors.GREY_500,
                    border_radius=15, 
                ),
            ]
        )
        return col

    def tambah_catatan(self, idCatatan,konten,halaman):
        if(int(halaman) > self.totalHalaman):
            self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh lebih besar dari total halaman buku!"))
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        self.kc.insert(Catatan(idCatatan,self.idBuku,halaman,konten))
        self.listCatatan = self.kc.get_all_catatan_per_buku(self.idBuku)

        self.update_and_sort_list()

    def tambah_catatan_pressed(self):
        dlg = FormUbahCatatan(self.page, 0, "Tambah Catatan",on_simpan=self.tambah_catatan)
        dlg.open = True
        self.page.dialog = dlg
        self.page.update()
        
  
    def delete_catatan(self, i):
        idCatatan = self.listCatatan[i].get_idCatatan()
        self.kc.delete_catatan(idCatatan, self.idBuku)
        self.listCatatan = self.kc.get_all_catatan_per_buku(self.idBuku)
        self.update_and_sort_list()

   
    def ubah_catatan(self, idCatatan,konten,halaman):

        if(int(halaman) > self.totalHalaman):
            self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh lebih besar dari total halaman buku!"))
            self.page.snack_bar.open = True
            self.page.update()
            return

        self.kc.edit_konten_halaman_catatan(self.idBuku, idCatatan, konten, halaman)
        self.listCatatan = self.kc.get_all_catatan_per_buku(self.idBuku)
       
        self.update_and_sort_list()

    

    def ubah_catattan_pressed(self, i):
        idCatatan = self.listCatatan[i].get_idCatatan()

        dlg = FormUbahCatatan(self.page, idCatatan, "Ubah Catatan" ,on_simpan=self.ubah_catatan,)
        dlg.open = True
        self.page.dialog = dlg
        self.page.update()
        dlg.open = False
       
    def update_and_sort_list(self):
        self.listCatatan.sort(key=lambda x: x.get_halamanBuku())
        self.list = self.build_list()
        self.page.clean()
        self.build()   

    def build_list(self):
        panel = ft.Column(
            auto_scroll=True,
            width=500,
            height=500,
            scroll=True,
            controls=[],  
        )

        for i in range(len(self.listCatatan)):
            exp = ft.ExpansionTile(
                visible=True,
                initially_expanded=False,
                # bgcolor=ft.colors.SECONDARY_CONTAINER,
                title=ft.Container(
                    # margin=10,
                    alignment=ft.alignment.center_left,
                    content=ft.Text(f"Page {self.listCatatan[i].get_halamanBuku()}", weight=ft.FontWeight.BOLD),
                ),
                controls=[
                    ft.Container(
                    margin=10,
                    # padding=10,
                    content=ft.Column(
                        [
                            ft.Container(
                                content=ft.Text(self.listCatatan[i].get_kontenCatatan()),
                            ),
                            ft.Container(
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=[
                                        ft.Container(
                                            width=100,
                                            height=30,
                                            margin=5,
                                            content=ft.FilledButton(
                                                text="Ubah",
                                                on_click=lambda e, i=i: self.ubah_catattan_pressed(i),
                                            ),
                                        ),
                                        ft.Container(
                                            width=100,
                                            height=30,
                                            margin=5,
                                            content=ft.FilledButton(
                                                text="Hapus",
                                                on_click=lambda e, i=i: self.delete_catatan(i),
                                            ),
                                        ),
                                    ]
                                )
                            )
                        ]
                    )
                ),
                ]
            )
            panel.controls.append(exp)
        return panel
    
# def main(page: ft.Page):
#     DisplayCatatan(9, page)


# ft.app(target=main)