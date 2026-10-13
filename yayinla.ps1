# Jarvis - GitHub'a yayinlama + Render/PWABuilder yol gosteren yardimci.
# Kullanim: yayinla.cmd dosyasina cift tikla.

$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot

function Find-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { return "git" }
    $p = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path $p) { return $p }
    return $null
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Jarvis - GitHub'a yayinlama yardimcisi" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$git = Find-Git
if (-not $git) {
    Write-Host "[X] Git bulunamadi. Kurun: https://git-scm.com/download/win" -ForegroundColor Red
    Read-Host "Kapatmak icin Enter"
    exit 1
}

# Yerel commit yoksa olustur
if (-not (Test-Path ".git")) { & $git init | Out-Null }
& $git branch -M main 2>$null
$status = & $git status --porcelain
if ($status) {
    Write-Host "[i] Degisiklikler commit ediliyor..."
    if (-not (& $git config user.name)) { & $git config user.name "Jarvis" }
    if (-not (& $git config user.email)) { & $git config user.email "jarvis@localhost" }
    & $git add -A
    & $git commit -m "Jarvis guncelleme" | Out-Null
}

$remote = & $git remote 2>$null
if ($remote -contains "origin") {
    Write-Host "[i] 'origin' zaten tanimli; guncellemeler gonderiliyor..."
    & $git push -u origin main
} else {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) {
        & gh auth status *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[i] GitHub giris yapilmamis. Giris penceresi aciliyor..." -ForegroundColor Yellow
            & gh auth login
        }
        $rname = Read-Host "GitHub repo adi (Enter = jarvis)"
        if ([string]::IsNullOrWhiteSpace($rname)) { $rname = "jarvis" }
        Write-Host "[i] Repo olusturulup gonderiliyor: $rname"
        & gh repo create $rname --public --source=. --remote=origin --push
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[!] gh ile gonderilemedi; manuel yola geciliyor." -ForegroundColor Yellow
        }
    }

    if (-not (& $git remote 2>$null | Select-String "origin")) {
        Write-Host ""
        Write-Host "GitHub'da BOS bir repo olusturun (README eklemeyin):" -ForegroundColor Yellow
        Write-Host "  https://github.com/new"
        Write-Host ""
        $url = Read-Host "Repo adresini yapistirin (https://github.com/KULLANICI/jarvis.git)"
        if ([string]::IsNullOrWhiteSpace($url)) {
            Write-Host "[X] Adres girilmedi." -ForegroundColor Red
            Read-Host "Kapatmak icin Enter"
            exit 1
        }
        & $git remote add origin $url
        & $git push -u origin main
    }
}

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Kod GitHub'a gonderildi! (branch: main)" -ForegroundColor Green
} else {
    Write-Host "[!] Gonderme tamamlanmamis olabilir; mesajlari kontrol edin." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "SONRAKI ADIMLAR" -ForegroundColor Cyan
Write-Host "1) Render (ucretsiz): https://render.com  -> New -> Web Service -> reponuzu secin" -ForegroundColor White
Write-Host "   Build : pip install -r requirements.txt"
Write-Host "   Start : python server.py"
Write-Host "   Env   : JARVIS_API_KEY=<anahtar>  JARVIS_MODEL=gemini-3-flash-preview  JARVIS_PROVIDER=gemini"
Write-Host "2) Cikan https adresini tarayicida acin (mikrofon izinlerini verin)."
Write-Host "3) APK: https://www.pwabuilder.com -> o https adresini girin -> Android paketi indirin."
Read-Host "Kapatmak icin Enter"
