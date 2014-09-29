# -*- mode: python -*-
a = Analysis(['UDSActorConfig.py'],
             pathex=['M:\\projects\\uds\\openuds\\windowsActor'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts + [('O','','OPTION')],
          a.binaries,
          a.zipfiles,
          a.datas,
          name='UDSActorConfig.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False, icon="uds.ico", manifest="UDSActorConfig_enterprise.manifest", version="UDSActorConfig_version_info.txt", append_pkg=True)
