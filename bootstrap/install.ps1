param([Parameter(Mandatory = $true)][string]$OutFile)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$url = 'https://github.com/RODRAX360/planeta-panetones-launcher/releases/download/launcher/PlanetaPanetones-Setup.exe'
$expectedSha256 = 'a9698ffe3b0701646be0c91b861513c84e8219ddcbb741b2bc84504a0c2006b4'
$expectedSize = 158251594

function Write-UpdateLog([string]$message) {
    if ($env:PP_UPDATE_LOG) {
        try { Add-Content -LiteralPath $env:PP_UPDATE_LOG -Value $message -Encoding UTF8 } catch {}
    }
}

function Download-Installer([string]$destination) {
    $client = New-Object System.Net.WebClient
    try { $client.DownloadFile($url, $destination) }
    finally { $client.Dispose() }
}

try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    try {
        Download-Installer $OutFile
    } catch {
        Write-UpdateLog ('Descarga con certificados de Windows falló: ' + $_.Exception.Message)
        Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
        # The downloaded installer is authenticated by the SHA-256 pinned below.
        # This fallback is scoped to this short-lived bootstrap process only.
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
        Download-Installer $OutFile
    }

    $actualSize = (Get-Item -LiteralPath $OutFile).Length
    if ($actualSize -ne $expectedSize) {
        throw "Tamaño del instalador inválido: $actualSize"
    }
    $actualHash = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedSha256) {
        throw "SHA-256 del instalador inválido: $actualHash"
    }
    Write-UpdateLog 'Instalador completo verificado con SHA-256.'
    $installer = Start-Process -FilePath $OutFile -ArgumentList '/S' -PassThru -Wait
    Write-UpdateLog ("Instalador completo finalizó con código $($installer.ExitCode).")
    exit $installer.ExitCode
} catch {
    Write-UpdateLog ('Rescate fallido: ' + $_.Exception.Message)
    Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
    exit 1
}
