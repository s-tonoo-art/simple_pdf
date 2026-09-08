import os
import sys
import queue
import threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from engine import SUPPORTED, merge, split, rotate, reader
from ordering import order_diagrams

HELP_TEXT = '''ファイルを追加
一覧へドラッグ＆ドロップ、または「ファイル追加」で選びます。
PDF・SVG・JPEG・PNG・BMP・TIFF・WebPに対応しています。

結合して保存
一覧のすべてのファイルを、上から順番に1つのPDFへ結合します。
画像1枚だけでもPDFにできます。「ファイル名をしおりにする」を
選ぶと、結合したPDFにファイル名のしおりが付きます。

順番の変更・除外
ファイルを選び「上に」「下に」で移動します。
「除外」は選択項目を、「クリア」は一覧すべてを取り除きます。
元のファイルは削除されません。
追加時は系統図を一覧の末尾へ、次の順に自動整列します。
その他 → システム系統図 → ケーブル系統図 → 空中線系統図
同じ種類はファイル名の数字順（1、2、10）で並びます。

1ページずつ分解
一覧からPDFを1つ選択し「1ページずつ分解」を押します。
保存先に新しい専用フォルダーを作り、各ページを保存します。

回転
一覧からPDFを1つ選択し、右90°・左90°・180°を選びます。
全ページを回転し、別名で保存します。

ページ数
PDFのページ数を自動表示します。「確認中」は読み込み中、
「読取不可」は保護や破損などで読み込めない状態です。
画像ファイルのページ数は「—」と表示します。

ショートカット
Ctrl+O：追加 ／ 一覧でCtrl+A：全選択 ／ Delete：除外
F1：使い方 ／ この画面でEsc：閉じる

保存・変換について
出力はPDFです。元ファイルと同じ名前・場所には保存できません。
画像の透過部分は白背景になります。
複雑なSVGの効果やフォントは、元と異なる場合があります。
パスワード入力が必要なPDFには対応していません。
'''

class App:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.events = queue.Queue()
        self.page_results = queue.Queue()
        root.title('シンプルPDF — 結合・分解・回転')
        root.geometry('920x580')
        root.minsize(720, 420)
        style = ttk.Style(root)
        style.theme_use('vista')
        style.configure('Treeview', rowheight=27, font=('Yu Gothic UI', 10))
        style.configure('TButton', padding=(9, 5))
        style.configure('Compact.TButton', padding=(3, 2))
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill='x')
        self.buttons = []
        for title, command in [('ファイル追加', self.add_dialog), ('結合して保存', self.do_merge), ('1ページずつ分解', self.do_split), ('右90°回転', lambda: self.do_rotate(90)), ('左90°回転', lambda: self.do_rotate(270)), ('180°回転', lambda: self.do_rotate(180))]:
            self.button(bar, title, command)
        self.help_window = None
        ttk.Button(bar, text='？', width=3, command=self.show_help).pack(side='right', padx=2)
        root.bind('<F1>', lambda e: self.show_help())
        ttk.Label(root, text='PDF・SVG・JPEG・PNGなどをここへドロップ  ／  結合は一覧の上から順番に、分解・回転は選択したPDFが対象', padding=(12, 5)).pack(anchor='w')
        frame = ttk.Frame(root, padding=(8, 0))
        frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('name', 'type', 'pages', 'path', 'date'), show='headings', selectmode='extended')
        for key, title, width in [('name', 'ファイル名', 250), ('type', '種類', 60), ('pages', 'ページ数', 70), ('path', 'フォルダー', 280), ('date', '更新日時', 145)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=50)
        self.tree.column('pages', anchor='center', stretch=False)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.paths = {}
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind('<<Drop>>', lambda e: self.add(root.tk.splitlist(e.data)))
        self.tree.bind('<Delete>', lambda e: self.remove())
        self.tree.bind('<Control-a>', lambda e: self.select_all())
        root.bind('<Control-o>', lambda e: self.add_dialog())
        bottom = ttk.Frame(root, padding=8)
        bottom.pack(fill='x')
        for title, command in [('上に', lambda: self.move(-1)), ('下に', lambda: self.move(1)), ('除外', self.remove), ('全選択', self.select_all), ('クリア', self.clear)]:
            self.button(bottom, title, command, compact=True)
        self.bookmarks = tk.BooleanVar()
        self.check = ttk.Checkbutton(bottom, text='ファイル名をしおりにする', variable=self.bookmarks)
        self.check.pack(side='left', padx=12)
        self.status = tk.StringVar(value='ファイルを追加してください')
        ttk.Label(root, textvariable=self.status, relief='sunken', padding=(8, 4)).pack(fill='x')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def button(self, parent, text, command, compact=False):
        options = {'width': 5, 'style': 'Compact.TButton'} if compact else {}
        button = ttk.Button(parent, text=text, command=command, **options)
        button.pack(side='left', padx=2)
        self.buttons.append(button)

    def show_help(self):
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.lift()
            self.help_window.focus_set()
            return
        window = self.help_window = tk.Toplevel(self.root)
        window.title('使い方 — シンプルPDF')
        window.geometry('650x590')
        window.minsize(480, 350)
        window.transient(self.root)
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        text = tk.Text(frame, wrap='word', font=('Yu Gothic UI', 10),
                       padx=12, pady=10, relief='solid', borderwidth=1)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        text.pack(fill='both', expand=True)
        text.insert('1.0', HELP_TEXT)
        text.configure(state='disabled')
        ttk.Button(window, text='閉じる', command=window.destroy).pack(pady=(0, 12))
        window.bind('<Escape>', lambda e: window.destroy())
        window.focus_set()

    def add_dialog(self):
        if not self.busy:
            self.add(filedialog.askopenfilenames(title='PDF・画像を追加', filetypes=[('PDF・画像', ' '.join('*'+x for x in sorted(SUPPORTED)))]))

    def add(self, paths):
        if self.busy:
            return
        errors = []
        page_jobs = []
        for value in paths:
            path = Path(value).resolve()
            if not path.is_file() or path.suffix.lower() not in SUPPORTED:
                errors.append(path.name)
                continue
            if str(path) in self.paths.values():
                continue
            try:
                date = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y/%m/%d %H:%M')
                is_pdf = path.suffix.lower() == '.pdf'
                item = self.tree.insert('', 'end', values=(path.name, path.suffix[1:].upper(), '確認中' if is_pdf else '—', str(path.parent), date))
                self.paths[item] = str(path)
                if is_pdf:
                    page_jobs.append((item, str(path)))
            except OSError as exc:
                errors.append(f'{path.name}: {exc}')
        ordered = order_diagrams([self.paths[i] for i in self.tree.get_children()])
        ids = {path: item for item, path in self.paths.items()}
        for index, path in enumerate(ordered):
            self.tree.move(ids[path], '', index)
        self.count()
        if page_jobs:
            threading.Thread(target=self.read_page_counts, args=(page_jobs,), daemon=True).start()
        if errors:
            messagebox.showwarning('追加できないファイル', '\n'.join(errors))

    def read_page_counts(self, jobs):
        for item, path in jobs:
            try:
                pages = len(reader(path).pages)
            except Exception:
                pages = '読取不可'
            self.page_results.put((item, path, pages))

    def update_page_counts(self):
        while True:
            try:
                item, path, pages = self.page_results.get_nowait()
            except queue.Empty:
                break
            if self.paths.get(item) == path:
                self.tree.set(item, 'pages', pages)

    def count(self):
        self.status.set(f'{len(self.paths)} ファイル  ｜  結合：一覧すべて ／ 分解・回転：PDFを1つ選択')

    def select_all(self):
        if not self.busy:
            self.tree.selection_set(self.tree.get_children())

    def remove(self):
        if self.busy:
            return
        for item in self.tree.selection():
            self.tree.delete(item)
            self.paths.pop(item)
        self.count()

    def clear(self):
        self.select_all()
        self.remove()

    def move(self, delta):
        if self.busy:
            return
        selected = set(self.tree.selection())
        items = list(self.tree.get_children())
        for item in items if delta < 0 else reversed(items):
            if item not in selected:
                continue
            index = self.tree.index(item)
            current = self.tree.get_children()
            other = index + delta
            if 0 <= other < len(current) and current[other] not in selected:
                self.tree.move(item, '', other)

    def pdf_selection(self):
        selected = self.tree.selection()
        if len(selected) != 1 or Path(self.paths[selected[0]]).suffix.lower() != '.pdf':
            messagebox.showinfo('対象の選択', '一覧からPDFを1つ選択してください。')
            return None
        return self.paths[selected[0]]

    def output(self, name):
        return filedialog.asksaveasfilename(title='別名で保存', initialfile=name, defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])

    def do_merge(self):
        paths = [self.paths[i] for i in self.tree.get_children()]
        if not paths:
            messagebox.showinfo('ファイルを追加', 'PDFまたは画像を追加してください。')
            return
        dest = self.output('結合.pdf')
        bookmarks = self.bookmarks.get()
        if dest:
            self.run(lambda: (merge(paths, dest, bookmarks), dest)[1])

    def do_split(self):
        path = self.pdf_selection()
        if path:
            directory = filedialog.askdirectory(title='分解ファイルの保存先（専用フォルダーを作成）')
            if directory:
                self.run(lambda: split(path, directory))

    def do_rotate(self, angle):
        path = self.pdf_selection()
        if path:
            dest = self.output(Path(path).stem + '_回転.pdf')
            if dest:
                self.run(lambda: (rotate(path, dest, angle), dest)[1])

    def run(self, operation):
        self.busy = True
        for button in self.buttons + [self.check]:
            button.configure(state='disabled')
        self.status.set('処理中です。しばらくお待ちください…')
        def worker():
            try:
                self.events.put((True, str(operation())))
            except Exception as exc:
                self.events.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        self.update_page_counts()
        try:
            ok, result = self.events.get_nowait()
            self.busy = False
            for button in self.buttons + [self.check]:
                button.configure(state='normal')
            self.status.set('保存しました：' + result if ok else '処理に失敗しました')
            if ok:
                messagebox.showinfo('完了', '保存しました。\n\n' + result)
            else:
                messagebox.showerror('処理できませんでした', result)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('処理中', '処理が終わってから閉じてください。')
        else:
            self.root.destroy()

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        import unittest
        import test_app
        with open(sys.argv[2], 'w', encoding='utf-8') as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_app))
        sys.exit(0 if result.wasSuccessful() else 1)
    root = TkinterDnD.Tk()
    app = App(root)
    app.add(sys.argv[1:])
    root.mainloop()
