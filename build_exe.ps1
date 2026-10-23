# build_exe.ps1 — Genera el ejecutable del puente con PyInstaller.
#
# Uso (desde la carpeta del proyecto, con el .venv de Python 3.12 creado):
#     .\build_exe.ps1
#
# Resultado:
#     dist\XoneK3Bridge\XoneK3Bridge.exe   <- el ejecutable (un solo archivo)
#     dist\XoneK3Bridge\config\            <- mapeos YAML, editables sin recompilar
#     dist\XoneK3Bridge.zip                <- todo lo anterior listo para compartir
#
# El driver teVirtualMIDI NO se empaqueta: lo instala loopMIDI en la PC donde se use.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No encontré $python. Creá el entorno: py -3.12 -m venv .venv; pip install -r requirements.txt"
}

& $python -m pip install -q -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias" }

$name = "XoneK3Bridge"
$out = "dist\$name"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }

# mido carga su backend (rtmidi) dinámicamente, así que hay que declararlo a mano.
& $python -m PyInstaller --noconfirm --clean --onefile --console `
    --name $name `
    --distpath $out `
    --workpath build `
    --specpath build `
    --paths src `
    --hidden-import mido.backends.rtmidi `
    --collect-submodules rtmidi `
    src\main.py
if ($LASTEXITCODE -ne 0) { throw "Falló PyInstaller" }

# config/ va al lado del .exe (no adentro) para poder editar el mapeo sin recompilar.
Copy-Item -Recurse config "$out\config"

$zip = "dist\$name.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path $out -DestinationPath $zip

Write-Host "`nListo:" -ForegroundColor Green
Write-Host "  $out\$name.exe"
Write-Host "  $zip"
