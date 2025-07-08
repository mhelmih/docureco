import flet as ft
import datetime as dt
from flet_route import Routing, path
from DetailBuku_page import DetailBuku
from DisplayCatatan import DisplayCatatan
from tambahBuku import Tambah_Buku
from CatatProgressPembacaan_page import CatatProgresPembacaan
from Main_Page import main

import sys

sys.path.append('.')
sys.path.append('./src')

def MainRouter(page: ft.Page):
    
    def display_catatan_view(page: ft.Page, params, basket):
        id_buku = int(params.get("id_buku"))
        display_catatan = DisplayCatatan(id_buku, page)

        view = ft.View(
            "/DisplayCatatan/:id_buku",
            controls = display_catatan.page.controls
        )
        return view
    
    detail_buku = DetailBuku()
    tambah_buku = Tambah_Buku()
    catat_progres_pembacaan = CatatProgresPembacaan()

    app_routes = [
        path(url="/", clear = True, view = main),
        path(url="/DetailBuku/:id_buku", clear = True, view = detail_buku.detail_buku),
        path(url="/DisplayCatatan/:id_buku", clear = True, view = display_catatan_view),
        path(url="/TambahBuku/", clear = True, view = tambah_buku.display_tambah_buku),
        path(url="/CatatProgresPembacaan/:id_buku", clear = True, view = catat_progres_pembacaan.catat_progress_pembacaan)
    ]

    Routing(page=page, app_routes=app_routes)

    page.go(page.route)

ft.app(target=MainRouter)