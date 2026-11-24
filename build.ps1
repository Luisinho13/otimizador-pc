# Gera dist\OtimizadorPC.exe com PyInstaller.
# Uso:  .\build.ps1            (roda os testes antes)
#       .\build.ps1 -SemTestes
param([switch]$SemTestes)

# Erros são verificados por $LASTEXITCODE: no PowerShell 5.1, 'Stop' trataria
# qualquer texto do PyInstaller no stderr como falha.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'Criando ambiente virtual (.venv)...'
    python -m venv .venv
    & $python -m pip install --quiet -r requirements-dev.txt
}

if (-not (Test-Path 'assets\icone.ico')) { & $python tools\gerar_icone.py }

if (-not $SemTestes) {
    Write-Host 'Rodando os testes...'
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam; build cancelado.' }
}

Write-Host 'Gerando o executável...'
& $python -m PyInstaller main.py `
    --name OtimizadorPC `
    --onefile `
    --windowed `
    --uac-admin `
    --icon assets\icone.ico `
    --add-data 'assets;assets' `
    --collect-data customtkinter `
    --version-file tools\versao.txt `
    --noconfirm --clean --log-level WARN
if ($LASTEXITCODE -ne 0) { throw 'O PyInstaller falhou.' }

$exe = Get-Item 'dist\OtimizadorPC.exe'
Write-Host ("Pronto: {0} ({1:N1} MB)" -f $exe.FullName, ($exe.Length / 1MB))
