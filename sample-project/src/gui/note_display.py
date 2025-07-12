import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import flet as ft
from src.note.note import Note
from src.note.note_collection import NoteCollection
from src.book.book_collection import BookCollection
from src.book.book import Book
from src.gui.edit_note_form import EditNoteForm

class NoteDisplay():
    def __init__(self, book_id, page : ft.Page):
        
        self.book_id = book_id
        self.page = page
        self.note_collection = NoteCollection()
        self.book_collection = BookCollection()
        self.note_collection.set_db("read_buddy.db")
        self.book_collection.set_db("read_buddy.db")
        self.note_list = self.note_collection.get_all_notes_per_book(book_id)
        self.book_title = (self.book_collection.get_by_id(book_id)).get_bookTitle()
        self.total_pages = (self.book_collection.get_by_id(book_id)).get_totalPages()

        self.list : ft.Column = self.build_list()
        self.build()
        self.update_and_sort_list()
       

    def build(self):
        # self.page.theme = ft.Theme(color_scheme_seed=ft.colors.WHITE)
        app_name = ft.Text(value="READ BUDDY", weight=ft.FontWeight.BOLD)
        page_title = ft.Text(self.book_title, weight=ft.FontWeight.BOLD,overflow=ft.TextOverflow.ELLIPSIS,)

        back_button = ft.ElevatedButton(text="Kembali", on_click= lambda _: self.page.go("/DetailBuku/" + str(self.book_id)))
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
                                        ft.IconButton(icon=ft.icons.ADD, on_click=lambda e: self.add_note_pressed()),
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
                        src = f"img/bookCover/cover{self.book_id}.jpg",
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
                    content=ft.Text(self.book_title,overflow=ft.TextOverflow.FADE,text_align=ft.TextAlign.CENTER,size=15,weight=ft.FontWeight.BOLD,color=ft.colors.WHITE),
                    bgcolor=ft.colors.GREY_500,
                    border_radius=15, 
                ),
            ]
        )
        return col

    def add_note(self, note_id, content, page):
        if(int(page) > self.total_pages):
            self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh lebih besar dari total halaman buku!"))
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        self.note_collection.insert(Note(note_id, self.book_id, page, content))
        self.note_list = self.note_collection.get_all_notes_per_book(self.book_id)

        self.update_and_sort_list()

    def add_note_pressed(self):
        dlg = EditNoteForm(self.page, 0, "Tambah Catatan", on_save=self.add_note)
        dlg.open = True
        self.page.dialog = dlg
        self.page.update()
        
  
    def delete_note(self, i):
        note_id = self.note_list[i].get_noteId()
        self.note_collection.delete_note(note_id, self.book_id)
        self.note_list = self.note_collection.get_all_notes_per_book(self.book_id)
        self.update_and_sort_list()

   
    def edit_note(self, note_id, content, page):

        if(int(page) > self.total_pages):
            self.page.snack_bar = ft.SnackBar(ft.Text("Halaman tidak boleh lebih besar dari total halaman buku!"))
            self.page.snack_bar.open = True
            self.page.update()
            return

        self.note_collection.edit_note_content_and_page(self.book_id, note_id, content, page)
        self.note_list = self.note_collection.get_all_notes_per_book(self.book_id)
       
        self.update_and_sort_list()

    

    def edit_note_pressed(self, i):
        note_id = self.note_list[i].get_noteId()

        dlg = EditNoteForm(self.page, note_id, "Ubah Catatan", on_save=self.edit_note,)
        dlg.open = True
        self.page.dialog = dlg
        self.page.update()
        dlg.open = False
       
    def update_and_sort_list(self):
        self.note_list.sort(key=lambda x: x.get_bookPage())
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

        for i in range(len(self.note_list)):
            exp = ft.ExpansionTile(
                visible=True,
                initially_expanded=False,
                # bgcolor=ft.colors.SECONDARY_CONTAINER,
                title=ft.Container(
                    # margin=10,
                    alignment=ft.alignment.center_left,
                    content=ft.Text(f"Page {self.note_list[i].get_bookPage()}", weight=ft.FontWeight.BOLD),
                ),
                controls=[
                    ft.Container(
                    margin=10,
                    # padding=10,
                    content=ft.Column(
                        [
                            ft.Container(
                                content=ft.Text(self.note_list[i].get_noteContent()),
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
                                                on_click=lambda e, i=i: self.edit_note_pressed(i),
                                            ),
                                        ),
                                        ft.Container(
                                            width=100,
                                            height=30,
                                            margin=5,
                                            content=ft.FilledButton(
                                                text="Hapus",
                                                on_click=lambda e, i=i: self.delete_note(i),
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