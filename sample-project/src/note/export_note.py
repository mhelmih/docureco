import os
import tkinter as tk
from tkinter import filedialog

def export_to_markdown(note_content: str, book_title: str):
    """
    Exports the given note content to a Markdown file.
    
    Args:
        note_content (str): The content of the note to be exported.
        book_title (str): The title of the book, used for the filename.
    """
    # Create a hidden root window for the file dialog
    root = tk.Tk()
    root.withdraw()
    
    # Sanitize the book title to create a valid filename
    safe_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '_')).rstrip()
    if not safe_title:
        safe_title = "Untitled_Note"
    
    # Open file dialog to choose save location
    file_path = filedialog.asksaveasfilename(
        initialdir=os.path.expanduser("~"), # Start in user's home directory
        initialfile=f"{safe_title}_notes.md",
        defaultextension=".md",
        filetypes=[("Markdown Files", "*.md"), ("All Files", "*.*")]
    )
    
    if file_path:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Notes for {book_title}\n\n")
                f.write(note_content)
            print(f"Note successfully exported to {file_path}")
            # Optionally, show a success message to the user
            # tk.messagebox.showinfo("Success", f"Note exported to {file_path}")
        except Exception as e:
            print(f"Error exporting note: {e}")
            # Optionally, show an error message
            # tk.messagebox.showerror("Error", f"Could not export note: {e}")

