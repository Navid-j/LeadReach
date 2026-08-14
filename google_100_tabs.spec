# -*- mode: python ; coding: utf-8 -*-
import os
import re as _re

from PyInstaller.utils.hooks import collect_all

# ---- version resource: read APP_VERSION from google_100_tabs.py and
# ---- generate the Windows version info file used by the exe metadata.
_src = open('google_100_tabs.py', encoding='utf-8').read()
_m = _re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _src)
APP_VERSION = _m.group(1) if _m else '1.0.0'
_vp = [int(x) for x in APP_VERSION.split('.')] + [0, 0, 0, 0]
version_file = os.path.join(SPECPATH, 'version_info.txt')

with open(version_file, 'w', encoding='utf-8') as _f:
    _f.write(f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({_vp[0]}, {_vp[1]}, {_vp[2]}, {_vp[3]}),
    prodvers=({_vp[0]}, {_vp[1]}, {_vp[2]}, {_vp[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'LeadReach'),
            StringStruct('FileDescription', 'LeadReach - Google link extractor and contact dashboard'),
            StringStruct('FileVersion', '{APP_VERSION}'),
            StringStruct('InternalName', 'google_100_tabs'),
            StringStruct('OriginalFilename', 'google_100_tabs.exe'),
            StringStruct('ProductName', 'LeadReach'),
            StringStruct('ProductVersion', '{APP_VERSION}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
''')

datas = []
binaries = []
hiddenimports = ['selenium.webdriver.chrome.webdriver', 'selenium.webdriver.common.by', 'selenium.webdriver.support.ui', 'selenium.webdriver.support.expected_conditions', 'urllib3', 'urllib3.packages', 'urllib3.packages.six']
tmp_ret = collect_all('selenium')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('requests')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['google_100_tabs.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='google_100_tabs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_file,
)
