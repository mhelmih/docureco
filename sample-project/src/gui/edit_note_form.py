import flet as ft


class EditNoteForm(ft.AlertDialog):
    def __init__(self, page : ft.Page, note_id, title, on_save, ):
        self.page_field = ft.TextField(label="Halaman",input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))
        self.note_content_field = ft.TextField(label="Konten Catatan", multiline=True, min_lines=3)
        super().__init__(

            title=ft.Text(title),
            content=ft.Container(
                expand=True,
                width=500,
                height=300,
                content=ft.Column(
                    controls=[
                        self.page_field,
                        self.note_content_field,
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
        self.on_save = on_save
        self.note_id = note_id
        

    def cancel(self, e):
        self.open = False
        self.page.update()

    def save(self, e):
        note_content = self.note_content_field.value
        page = self.page_field.value
        self.open = False
        self.page.update()
        self.on_save(self.note_id, note_content, page)

