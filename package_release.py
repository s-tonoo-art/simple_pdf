from pathlib import Path
import importlib.metadata as metadata
import shutil
import sys
import zipfile

base = Path(__file__).resolve().parent
release = base / 'release'
release.mkdir(exist_ok=True)
licenses = release / 'licenses'
licenses.mkdir(exist_ok=True)
packages = ['pypdf', 'pillow', 'svglib', 'reportlab', 'tkinterdnd2', 'lxml', 'cssselect2', 'tinycss2', 'webencodings', 'charset-normalizer', 'numpy', 'cryptography', 'cffi', 'pycparser', 'fonttools', 'pyinstaller']
index = []
for name in packages:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    index.append(f'{dist.metadata["Name"]} {dist.version}')
    for file in dist.files or []:
        if any(word in str(file).lower() for word in ('license', 'copying', 'notice')) and Path(dist.locate_file(file)).is_file():
            dest = licenses / name / str(file)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dist.locate_file(file), dest)
for source, name in [(Path(sys.base_prefix) / 'LICENSE.txt', 'Python.txt'), (Path(sys.base_prefix) / 'tcl/tcl8.6/license.terms', 'Tcl.txt'), (Path(sys.base_prefix) / 'tcl/tk8.6/license.terms', 'Tk.txt')]:
    if source.exists():
        shutil.copyfile(source, licenses / name)
(licenses / 'INDEX.txt').write_text('\n'.join(index), encoding='utf-8')
shutil.copyfile(base / 'dist/SimplePDF.exe', release / 'SimplePDF.exe')
shutil.copyfile(base / 'README.md', release / '使い方.txt')
with zipfile.ZipFile(base / 'SimplePDF_配布用.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in release.rglob('*'):
        if file.is_file():
            archive.write(file, file.relative_to(release))
print(base / 'SimplePDF_配布用.zip')
