# -*- coding: utf-8 -*-
<#
  Wikelo OCR – Wortbox-Dumper
  Liest per eingebauter Windows-OCR (Windows.Media.Ocr, offline) alle
  Inventar-Screenshots und schreibt JEDES erkannte Wort mit Position/Groesse
  nach SC_Wikelo_OCR_words.json.  Das ist die Rohdaten-Basis fuer den Matcher.

  Aufruf:
    powershell -ExecutionPolicy Bypass -File wikelo_ocr_dump.ps1
    (optional)  -Pattern "inventar*.png"   -Folder "<Pfad>"

  Standard: verarbeitet alle Dateien, die auf  inventar*.png / *.png  im
  angegebenen Ordner passen (Reihenfolge = Dateiname = Screenshot-Reihenfolge).
#>
param(
  [string]$Folder  = $PSScriptRoot,
  [string]$Pattern = "inventar*.png",
  [string]$Out     = (Join-Path $PSScriptRoot "SC_Wikelo_OCR_words.json")
)

# ---- WinRT + Await-Bruecke (PS 5.1) ----
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile,Windows.Foundation,ContentType=WindowsRuntime]
try { Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop }
catch { [System.Reflection.Assembly]::LoadWithPartialName("System.Runtime.WindowsRuntime") | Out-Null }

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op,$t){
  $m = $asTaskGeneric.MakeGenericMethod($t)
  $task = $m.Invoke($null,@($op)); $task.Wait(-1) | Out-Null; $task.Result
}

# ---- OCR-Engine (erst Profil-Sprache, sonst Englisch) ----
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if(-not $engine){
  $lang = New-Object Windows.Globalization.Language "en-US"
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
}
if(-not $engine){ Write-Error "Keine Windows-OCR-Sprache verfuegbar."; exit 2 }
Write-Host ("OCR-Sprache: " + $engine.RecognizerLanguage.DisplayName)

function Ocr-Words($path){
  $sf     = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
  $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $dec    = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bmp    = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $res    = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
  $w = [int]$dec.PixelWidth; $h = [int]$dec.PixelHeight
  $words = New-Object System.Collections.ArrayList
  foreach($line in $res.Lines){
    foreach($word in $line.Words){
      $r = $word.BoundingRect
      [void]$words.Add([ordered]@{
        text=$word.Text; x=[math]::Round($r.X,1); y=[math]::Round($r.Y,1);
        w=[math]::Round($r.Width,1); h=[math]::Round($r.Height,1)
      })
    }
  }
  return [ordered]@{ imgW=$w; imgH=$h; words=$words }
}

$files = Get-ChildItem -Path $Folder -Filter $Pattern -File | Sort-Object Name
if(-not $files){ Write-Error "Keine Screenshots gefunden ($Pattern in $Folder)."; exit 1 }

$pages = New-Object System.Collections.ArrayList
foreach($f in $files){
  Write-Host ("OCR: " + $f.Name)
  $p = Ocr-Words $f.FullName
  $p.file = $f.Name
  [void]$pages.Add($p)
  Write-Host ("   " + $p.words.Count + " Woerter, Bild " + $p.imgW + "x" + $p.imgH)
}

$payload = [ordered]@{ generated=(Get-Date -Format s); folder=$Folder; pattern=$Pattern; pages=$pages }
$payload | ConvertTo-Json -Depth 8 | Out-File -FilePath $Out -Encoding utf8
Write-Host ("geschrieben: " + $Out)
