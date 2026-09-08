"""Local PDF operations; inputs are never overwritten."""
import io
import os
import tempfile
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageOps, ImageSequence
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from svglib.fonts import register_font

SUPPORTED = {'.pdf', '.svg', '.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}

def setup_svg_fonts():
    font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msgothic.ttc'
    if font.exists() and 'WindowsJapanese' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('WindowsJapanese', str(font), subfontIndex=0))
        for family in ('MS Gothic', 'MS PGothic', 'ＭＳ ゴシック', 'ＭＳ Ｐゴシック', 'メイリオ', 'Meiryo', 'sans-serif', 'serif', 'monospace', 'Arial', 'Helvetica'):
            register_font(family, font_path=str(font), rlgFontName='WindowsJapanese')

def reader(path):
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        result = PdfReader(io.BytesIO(path.read_bytes()))
        if result.is_encrypted and not result.decrypt(''):
            raise ValueError(f'{path.name}: パスワード保護されたPDFには対応していません。')
        return result
    stream = io.BytesIO()
    if path.suffix.lower() == '.svg':
        setup_svg_fonts()
        drawing = svg2rlg(str(path))
        if drawing is None or drawing.width <= 0 or drawing.height <= 0:
            raise ValueError(f'{path.name}: SVGを読み込めません。')
        renderPDF.drawToFile(drawing, stream)
    else:
        with Image.open(path) as original:
            frames = []
            for frame in ImageSequence.Iterator(original):
                rgba = ImageOps.exif_transpose(frame).convert('RGBA')
                white = Image.new('RGB', rgba.size, 'white')
                white.paste(rgba, mask=rgba.getchannel('A'))
                frames.append(white)
            frames[0].save(stream, format='PDF', save_all=True, append_images=frames[1:], resolution=96)
    stream.seek(0)
    return PdfReader(stream)

def save(writer, destination, sources):
    destination = Path(destination).resolve()
    if any(destination == Path(p).resolve() for p in sources):
        raise ValueError('元ファイルと同じ場所には保存できません。別の名前を指定してください。')
    fd, temp = tempfile.mkstemp(suffix='.pdf', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            writer.write(out)
        os.replace(temp, destination)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def merge(paths, destination, bookmarks=False):
    with PdfWriter() as writer:
        for path in paths:
            try:
                writer.append(reader(path), outline_item=Path(path).stem if bookmarks else None)
            except Exception as exc:
                raise ValueError(f'{Path(path).name}\n{exc}') from exc
        save(writer, destination, paths)

def rotate(path, destination, angle):
    with PdfWriter() as writer:
        writer.clone_document_from_reader(reader(path))
        for page in writer.pages:
            page.rotate(angle)
        save(writer, destination, [path])

def split(path, directory):
    source = reader(path)
    # A unique subfolder prevents overwriting an earlier split.
    folder = Path(tempfile.mkdtemp(prefix=Path(path).stem + '_分解_', dir=directory))
    try:
        for index, page in enumerate(source.pages, 1):
            with PdfWriter() as writer:
                writer.add_page(page)
                save(writer, folder / f'{index:04d}.pdf', [path])
    except Exception:
        for generated in folder.glob('*.pdf'):
            generated.unlink()
        folder.rmdir()
        raise
    return folder
