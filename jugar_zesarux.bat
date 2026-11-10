@echo off
cd /d "%~dp0tools\ZEsarUX_windows-13.0"
start zesarux.exe --machine CPC6128 --enable-dsk --dsk-file "..\..\bluesb.dsk" --enable-remoteprotocol --remoteprotocol-port 10010
