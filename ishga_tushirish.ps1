# ==========================================================================
#  Rasch Math Platform — bitta buyruq bilan to'liq ishga tushirish
# --------------------------------------------------------------------------
#  Bajaradi:
#    1. eski jarayonlarni to'xtatadi;
#    2. cloudflared tunnelini ochadi va HTTPS manzilni oladi;
#    3. .env dagi PUBLIC_BASE_URL / ALLOWED_HOSTS / CSRF ni yangilaydi;
#    4. Django serverini ishga tushiradi;
#    5. Telegram botni ishga tushiradi;
#    6. hammasi ishlayotganini tekshiradi va manzillarni chiqaradi.
#
#  Foydalanish:
#      powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1
#
#  To'xtatish:
#      powershell -ExecutionPolicy Bypass -File .\toxtatish.ps1
# ==========================================================================

param(
    [int]$Port = 8000,
    [switch]$NoBot,
    [switch]$UseNgrok
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

function Say($text, $color = "White") { Write-Host $text -ForegroundColor $color }

Say ""
Say "=====================================================" Cyan
Say "  RASCH MATH PLATFORM — ishga tushirish" Cyan
Say "=====================================================" Cyan

# --------------------------------------------------------------------------
#  0. Tayyorgarlik
# --------------------------------------------------------------------------
if (-not (Test-Path ".\logs")) { New-Item -ItemType Directory ".\logs" | Out-Null }
if (-not (Test-Path ".\.env")) {
    Say "[XATO] .env fayli topilmadi. .env.example dan nusxa oling." Red
    exit 1
}

$python = "python"
if (Test-Path ".\env\Scripts\python.exe") { $python = ".\env\Scripts\python.exe" }
Say "[i] Python: $python" DarkGray

# --------------------------------------------------------------------------
#  1. Eski jarayonlarni to'xtatish
# --------------------------------------------------------------------------
Say "[1/6] Eski jarayonlar to'xtatilmoqda..." Yellow

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "runserver|run_bot" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 2

# --------------------------------------------------------------------------
#  2. Tunnel
# --------------------------------------------------------------------------
$publicUrl = ""

if ($UseNgrok) {
    Say "[2/6] ngrok tunneli ochilmoqda..." Yellow
    if (-not (Test-Path ".\tools\ngrok.exe")) {
        Say "[XATO] tools\ngrok.exe topilmadi." Red
        exit 1
    }
    Start-Process -FilePath ".\tools\ngrok.exe" `
        -ArgumentList "http", "$Port", "--log=stdout" `
        -WindowStyle Hidden -RedirectStandardOutput ".\logs\ngrok.log"
    Start-Sleep -Seconds 8
    try {
        $api = Invoke-RestMethod "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 15
        $publicUrl = ($api.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
    } catch { $publicUrl = "" }
    Say "[!] Diqqat: ngrok bepul tarifida brauzer ogohlantirish sahifasi chiqadi." Yellow
    Say "    Telegram Mini App uchun cloudflared tavsiya etiladi (-UseNgrok siz)." Yellow
}
else {
    Say "[2/6] cloudflared tunneli ochilmoqda..." Yellow
    if (-not (Test-Path ".\tools\cloudflared.exe")) {
        Say "    cloudflared yuklab olinmoqda (~54 MB)..." DarkGray
        $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $url -OutFile ".\tools\cloudflared.exe" -UseBasicParsing -TimeoutSec 600
        } catch {
            Say "[XATO] cloudflared yuklab olinmadi: $($_.Exception.Message)" Red
            exit 1
        }
    }

    Remove-Item ".\logs\cloudflared.log" -ErrorAction SilentlyContinue
    Start-Process -FilePath ".\tools\cloudflared.exe" `
        -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$Port", "--logfile", ".\logs\cloudflared.log" `
        -WindowStyle Hidden

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        $log = Get-Content ".\logs\cloudflared.log" -Raw -ErrorAction SilentlyContinue
        $match = [regex]::Match([string]$log, "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) { $publicUrl = $match.Value; break }
    }
}

if (-not $publicUrl) {
    Say "[XATO] Tunnel manzili olinmadi. logs\ ichidagi log faylini tekshiring." Red
    exit 1
}
Say "      Tunnel: $publicUrl" Green

# --------------------------------------------------------------------------
#  3. .env ni yangilash
# --------------------------------------------------------------------------
Say "[3/6] .env yangilanmoqda..." Yellow
& $python ".\tools\set_public_url.py" $publicUrl
if (-not $?) { Say "[XATO] .env yangilanmadi." Red; exit 1 }

# --------------------------------------------------------------------------
#  4. Django server
# --------------------------------------------------------------------------
Say "[4/6] Django serveri ishga tushmoqda (port $Port)..." Yellow
& $python "manage.py" "migrate" "--noinput" | Out-Null
Start-Process -FilePath $python `
    -ArgumentList "manage.py", "runserver", "127.0.0.1:$Port", "--noreload" `
    -WindowStyle Hidden -RedirectStandardOutput ".\logs\django.log" -RedirectStandardError ".\logs\django.err.log"
Start-Sleep -Seconds 6

# --------------------------------------------------------------------------
#  5. Telegram bot
# --------------------------------------------------------------------------
if ($NoBot) {
    Say "[5/6] Bot o'tkazib yuborildi (-NoBot)." DarkGray
} else {
    Say "[5/6] Telegram bot ishga tushmoqda..." Yellow
    Start-Process -FilePath $python `
        -ArgumentList "run_bot.py" `
        -WindowStyle Hidden -RedirectStandardOutput ".\logs\bot.out.log" -RedirectStandardError ".\logs\bot.err.log"
    Start-Sleep -Seconds 10
}

# --------------------------------------------------------------------------
#  6. Tekshirish
# --------------------------------------------------------------------------
Say "[6/6] Tekshirilmoqda..." Yellow
$ok = $true
$browserUA = @{ "User-Agent" = "Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile Safari/537.36" }

# Tunnel DNS yozuvi tarqalishi uchun bir necha soniya kerak bo'lishi mumkin.
Say "      Tunnel ochilishi kutilmoqda..." DarkGray
$ready = $false
for ($i = 0; $i -lt 24; $i++) {
    try {
        $probe = Invoke-WebRequest -Uri "$publicUrl/sog/" -UseBasicParsing -TimeoutSec 12 -Headers $browserUA
        if ($probe.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        Start-Sleep -Seconds 5
    }
}

if (-not $ready) {
    Say "      [!] Tunnel javob bermadi. logs\cloudflared.log ni tekshiring." Red
    $ok = $false
} else {
    foreach ($path in @("/", "/app/", "/panel/kirish/", "/verify/")) {
        try {
            $response = Invoke-WebRequest -Uri "$publicUrl$path" -UseBasicParsing -TimeoutSec 25 -Headers $browserUA
            Say ("      {0,-18} {1}" -f $path, $response.StatusCode) Green
        } catch {
            Say ("      {0,-18} XATO: {1}" -f $path, $_.Exception.Message) Red
            $ok = $false
        }
    }
}

if (-not $NoBot) {
    Start-Sleep -Seconds 3
    $botLog = ""
    foreach ($file in @(".\logs\bot.err.log", ".\logs\bot.out.log")) {
        if (Test-Path $file) {
            try {
                $stream = [System.IO.File]::Open($file, "Open", "Read", "ReadWrite")
                $reader = New-Object System.IO.StreamReader($stream)
                $botLog += $reader.ReadToEnd()
                $reader.Close(); $stream.Close()
            } catch { }
        }
    }
    if ($botLog -match "Bot ishga tushdi") { Say "      Bot:               ishga tushdi" Green }
    else { Say "      [!] Bot ishga tushmadi — logs\bot.err.log ni tekshiring" Red; $ok = $false }
    if ($botLog -match "menyu tugmasi o'rnatildi") { Say "      Web ilova tugmasi: o'rnatildi" Green }
    if ($botLog -match "Mini App o'chirilgan") { Say "      [!] Mini App o'chiq - PUBLIC_BASE_URL tekshiring" Red; $ok = $false }
    if ($botLog -match "Conflict") { Say "      [!] Botning boshqa nusxasi ishlayapti - uni to'xtating" Red }
}

Say ""
Say "=====================================================" Cyan
if ($ok) { Say "  TAYYOR" Green } else { Say "  QISMAN TAYYOR — loglarni tekshiring" Yellow }
Say "=====================================================" Cyan
Say ""
Say "  Web ilova      : $publicUrl/app/"
Say "  Boshqaruv      : $publicUrl/panel/"
Say "  Panel (Telegram): $publicUrl/panel/tg/"
Say "  Sertifikat     : $publicUrl/verify/"
Say "  Lokal          : http://127.0.0.1:$Port/"
Say ""
Say "  Loglar        : logs\bot.err.log, logs\django.log, logs\cloudflared.log" DarkGray
Say "  To'xtatish    : .\toxtatish.ps1" DarkGray
Say ""
Say "  Eslatma: tunnel manzili har safar o'zgaradi — bu skript uni" DarkGray
Say "  .env ga avtomatik yozadi va botni yangi manzil bilan qayta ishga tushiradi." DarkGray
Say ""
