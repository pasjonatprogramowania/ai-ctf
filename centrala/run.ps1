# Uruchomienie Centrali CTF + utworzenie zespołu (Windows PowerShell).
# Uzycie:  .\run.ps1 [-Port 8080] [-NewTeam]
param(
    [int]$Port = 8080,
    [switch]$NewTeam
)

$py = if ($env:CTF_PYTHON) { $env:CTF_PYTHON } else { "python" }
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($NewTeam) {
    & $py "$here\server.py" --new-team --port $Port | Tee-Object -Variable out
    $key = ($out | Select-String -Pattern 'Nowy klucz API: (.+)').Matches[0].Groups[1].Value
    if ($key) { Set-Content "$here\.apikey" $key -NoNewline; Write-Host "Klucz zapisany w .apikey: $key" }
    exit 0
}

Write-Host "Start Centrali na porcie $Port (panel: http://127.0.0.1:$Port/)"
& $py "$here\server.py" --port $Port
