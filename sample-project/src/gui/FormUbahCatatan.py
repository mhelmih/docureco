import flet as ft


class FormUbahCatatan(ft.AlertDialog):
    def __init__(self, page : ft.Page, idCatatan,title,on_simpan, ):
        self.halaman_field = ft.TextField(label="Halaman",input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))
        self.catatan_content_field = ft.TextField(label="Konten Catatan", multiline=True, min_lines=3)
        super().__init__(

            title=ft.Text(title),
            content=ft.Container(
                expand=True,
                width=500,
                height=300,
                content=ft.Column(
                    controls=[
                        self.halaman_field,
                        self.catatan_content_field,
                    ]
                )
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.cancel),
                ft.TextButton("Simpan", on_click=self.save),
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page = page
        self.on_simpan = on_simpan
        self.idCatatan = idCatatan
        

    def cancel(self, e):
        self.open = False
        self.page.update()

    def save(self, e):
        catatan_content = self.catatan_content_field.value
        halaman = self.halaman_field.value
        self.open = False
        self.page.update()
        self.on_simpan(self.idCatatan,catatan_content, halaman)

