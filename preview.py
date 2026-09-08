"""Capture only this application's own window for layout review."""
from pathlib import Path
from PIL import ImageGrab
from tkinterdnd2 import TkinterDnD
from app import App
import ctypes

root = TkinterDnD.Tk()
app = App(root)
root.update()
root.after(500, lambda: (ImageGrab.grab(window=ctypes.windll.user32.GetParent(root.winfo_id())).save(Path(__file__).parent / 'preview.png'), root.destroy()))
root.mainloop()
