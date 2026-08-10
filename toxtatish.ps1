# ==========================================================================
#  Rasch Math Platform — barcha jarayonlarni to'xtatish
#
#      powershell -ExecutionPolicy Bypass -File .\toxtatish.ps1
# ==========================================================================

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

Write-Host ""
Write-Host "Jarayonlar to'xtatilmoqda..." -ForegroundColor Yellow

$stopped = 0

Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  cloudflared (PID $($_.Id)) to'xtatildi" -ForegroundColor DarkGray
    $stopped++
}

Get-Process ngrok -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  ngrok (PID $($_.Id)) to'xtatildi" -ForegroundColor DarkGray
    $stopped++
}

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "runserver|run_bot" } |
    ForEach-Object {
        $label = if ($_.CommandLine -match "run_bot") { "bot" } else { "django" }
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  $label (PID $($_.ProcessId)) to'xtatildi" -ForegroundColor DarkGray
        $stopped++
    }

Write-Host ""
if ($stopped -gt 0) {
    Write-Host "$stopped ta jarayon to'xtatildi." -ForegroundColor Green
} else {
    Write-Host "Ishlayotgan jarayon topilmadi." -ForegroundColor DarkGray
}
Write-Host ""
