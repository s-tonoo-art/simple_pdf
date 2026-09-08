import hashlib
import tempfile
import unittest
import time
from pathlib import Path
from PIL import Image
from pypdf import PdfWriter, PdfReader
from engine import merge, split, rotate

class Operations(unittest.TestCase):
    def test_diagram_order(self):
        from ordering import order_diagrams
        paths = ['1_表紙.pdf', '2_目次.pdf', '空中線系統図(A)_10.svg', 'その他.pdf', 'ケーブル系統図(A)_2.svg', 'システム系統図(A)_2.svg', '空中線系統図(A)_2.svg', 'システム系統図(A)_1.svg', '末尾.pdf']
        self.assertEqual(order_diagrams(paths), ['1_表紙.pdf', '2_目次.pdf', 'その他.pdf', '末尾.pdf', 'システム系統図(A)_1.svg', 'システム系統図(A)_2.svg', 'ケーブル系統図(A)_2.svg', '空中線系統図(A)_2.svg', '空中線系統図(A)_10.svg'])

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            source = d / '元 PDF.pdf'
            w = PdfWriter()
            w.add_blank_page(width=240, height=320)
            w.add_blank_page(width=300, height=400)
            w.write(source)
            original = hashlib.sha256(source.read_bytes()).digest()
            Image.new('RGBA', (96, 192), (255, 0, 0, 120)).save(d / '透過.png')
            Image.new('RGB', (192, 96), 'blue').save(d / 'photo.jpeg')
            (d / 'vector.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="green"/><circle cx="100" cy="50" r="30" fill="orange"/></svg>')
            inputs = [source, d / '透過.png', d / 'vector.svg', d / 'photo.jpeg']
            result = d / 'merged.pdf'
            merge(inputs, result, True)
            r = PdfReader(result)
            self.assertEqual(len(r.pages), 5)
            self.assertEqual(len(r.outline), 4)
            self.assertEqual(float(r.pages[0].mediabox.width), 240)
            self.assertEqual(float(r.pages[2].mediabox.width), 72)
            self.assertEqual(float(r.pages[3].mediabox.width), 150)
            for angle in (90, 180, 270):
                rotate(result, d / 'rotated.pdf', angle)
                self.assertTrue(all(p.rotation == angle for p in PdfReader(d / 'rotated.pdf').pages))
            folder = split(result, d)
            self.assertEqual(len(list(folder.glob('*.pdf'))), 5)
            self.assertTrue(all(len(PdfReader(p).pages) == 1 for p in folder.glob('*.pdf')))
            self.assertNotEqual(folder, split(result, d))
            with self.assertRaises(ValueError):
                merge(inputs, source)
            (d / 'broken.pdf').write_bytes(b'broken')
            previous = result.read_bytes()
            with self.assertRaises(Exception):
                merge([source, d / 'broken.pdf'], result)
            self.assertEqual(previous, result.read_bytes())
            self.assertEqual(original, hashlib.sha256(source.read_bytes()).digest())

    def test_svg_japanese(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / '日本語.svg'
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"><text x="10" y="40" font-family="MS Gothic" font-size="20">システム系統図</text></svg>', encoding='utf-8')
            dest = Path(temp) / 'out.pdf'
            merge([path], dest)
            self.assertIn('システム系統図', PdfReader(dest).pages[0].extract_text())

    def test_ui(self):
        from tkinterdnd2 import TkinterDnD
        from app import App
        root = TkinterDnD.Tk()
        root.withdraw()
        app = App(root)
        with tempfile.TemporaryDirectory(prefix='日本語 空白 ') as temp:
            paths = []
            for i in range(4):
                path = Path(temp) / f'{i}.png'
                Image.new('RGB', (10, 10)).save(path)
                paths.append(str(path))
            app.add(root.tk.splitlist(root.tk.call('list', *paths)))
            items = app.tree.get_children()
            app.tree.selection_set(items[:2])
            app.move(-1)
            self.assertEqual(app.tree.get_children(), items)
            app.move(1)
            self.assertEqual(app.tree.get_children(), (items[2], items[0], items[1], items[3]))
            app.clear()
            self.assertFalse(app.paths)
            pdf = Path(temp) / '3ページ.pdf'
            with PdfWriter() as writer:
                for _ in range(3):
                    writer.add_blank_page(width=100, height=100)
                writer.write(pdf)
            broken = Path(temp) / '破損.pdf'
            broken.write_bytes(b'broken')
            app.add([str(pdf), str(broken), paths[0]])
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                app.update_page_counts()
                rows = [str(app.tree.set(i, 'pages')) for i in app.tree.get_children()]
                if '確認中' not in rows:
                    break
                time.sleep(0.01)
            self.assertEqual(rows, ['3', '読取不可', '—'])
            app.clear()
            # Results arriving after a row is removed must be ignored.
            app.page_results.put(('removed', str(pdf), 3))
            app.update_page_counts()
        root.destroy()

if __name__ == '__main__':
    unittest.main()
