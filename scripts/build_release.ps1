[CmdletBinding()]
param(
    [switch]$SkipTests,
    [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonCommand = Get-Command $PythonExecutable -ErrorAction Stop

Push-Location $repositoryRoot
try {
    if (-not $SkipTests) {
        & $pythonCommand.Source -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    }

    $distDirectory = Join-Path $repositoryRoot "dist"
    New-Item -ItemType Directory -Path $distDirectory -Force | Out-Null
    Get-ChildItem -LiteralPath $distDirectory -File | Where-Object {
        $_.Name -match '^(neomapper-.*\.(whl|tar\.gz)|NEOMapper-.*\.(zip|exe)|(?:Manual_do_Usuario_NEOMapper_|Manual_del_Usuario_NEOMapper_|NEOMapper_User_Manual_).*\.docx|SHA256SUMS\.txt)$'
    } | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
    }

    & $pythonCommand.Source -m build
    if ($LASTEXITCODE -ne 0) { throw "Python package build failed." }

    & $pythonCommand.Source -m twine check dist\*.whl dist\*.tar.gz
    if ($LASTEXITCODE -ne 0) { throw "Package metadata validation failed." }

    $version = & $pythonCommand.Source -c "from neomapper.shared.version import APP_VERSION; print(APP_VERSION)"
    & $pythonCommand.Source scripts\build_user_manual.py
    if ($LASTEXITCODE -ne 0) { throw "User manual build failed." }
    $manualSource = Join-Path $repositoryRoot "docs\Manual_do_Usuario_NEOMapper_$version.docx"
    @(
        @{ Language = "en"; Name = "NEOMapper_User_Manual_$version.docx" },
        @{ Language = "es"; Name = "Manual_del_Usuario_NEOMapper_$version.docx" }
    ) | ForEach-Object {
        $translatedManual = Join-Path $repositoryRoot "docs\$($_.Name)"
        & $pythonCommand.Source scripts\translate_user_manual.py $_.Language $manualSource $translatedManual
        if ($LASTEXITCODE -ne 0) { throw "User manual translation failed for $($_.Language)." }
    }

    & $pythonCommand.Source -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name NEOMapper `
        --icon (Join-Path (Get-Location) "src\neomapper\presentation\data\neomapper_icon.ico") `
        --specpath build `
        --paths src `
        --collect-data neomapper.presentation `
        --collect-data astroquery `
        --collect-data pyvo `
        --copy-metadata imageio `
        src\neomapper\__main__.py
    if ($LASTEXITCODE -ne 0) { throw "Windows application build failed." }

    @(
        "dist\NEOMapper\_internal\neomapper\presentation\data\hipparcos_bright.npz",
        "dist\NEOMapper\_internal\neomapper\presentation\locales\en.json",
        "dist\NEOMapper\_internal\astroquery\CITATION",
        "dist\NEOMapper\_internal\pyvo\samp\data\astropy_icon.png"
    ) | ForEach-Object {
        if (-not (Test-Path -LiteralPath $_)) {
            throw "Required runtime resource is missing from the Windows build: $_"
        }
    }
    if (-not (Test-Path -Path "dist\NEOMapper\_internal\imageio-*.dist-info\METADATA")) {
        throw "Required imageio package metadata is missing from the Windows build."
    }
    Copy-Item -LiteralPath "LICENSE" -Destination "dist\NEOMapper\LICENSE.txt" -Force
    Copy-Item -LiteralPath "THIRD_PARTY_NOTICES.md" -Destination "dist\NEOMapper\THIRD_PARTY_NOTICES.md" -Force

    # The Python runtime can contribute an older app-local MSVC runtime. Once
    # loaded by the bootloader, that copy shadows the newer runtime required by
    # Qt and causes WinError 127 while importing QtCore. Promote Qt's compatible
    # copies to the application runtime directory.
    @("VCRUNTIME140.dll", "VCRUNTIME140_1.dll") | ForEach-Object {
        $qtRuntime = Join-Path "dist\NEOMapper\_internal\PySide6" $_
        if (Test-Path -LiteralPath $qtRuntime) {
            Copy-Item -LiteralPath $qtRuntime -Destination "dist\NEOMapper\_internal\$_" -Force
        }
    }

    # Python distributions can ship ICU DLLs that share Qt's dependency names
    # but export a different ABI. Qt for Windows intentionally uses the ICU
    # implementation from System32, so these unrelated copies must not be
    # present beside the frozen application.
    @("icuuc.dll", "icudt*.dll", "icuin.dll") | ForEach-Object {
        Get-ChildItem -Path "dist\NEOMapper\_internal\$_" -File -ErrorAction SilentlyContinue |
            Remove-Item -Force
    }

    $runtimeTest = Start-Process `
        -FilePath "dist\NEOMapper\NEOMapper.exe" `
        -ArgumentList "--self-test-animation-runtime" `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($runtimeTest.ExitCode -ne 0) {
        throw "Frozen GIF/MP4 runtime self-test failed."
    }

    $mapRuntimeTest = Start-Process `
        -FilePath "dist\NEOMapper\NEOMapper.exe" `
        -ArgumentList "--self-test-map-runtime" `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($mapRuntimeTest.ExitCode -ne 0) {
        throw "Frozen Cartopy/PROJ runtime self-test failed."
    }

    $manuals = @(
        "Manual_do_Usuario_NEOMapper_$version.docx",
        "NEOMapper_User_Manual_$version.docx",
        "Manual_del_Usuario_NEOMapper_$version.docx"
    ) | ForEach-Object { Join-Path $repositoryRoot "docs\$_" }
    $missingManuals = @($manuals | Where-Object { -not (Test-Path -LiteralPath $_) })
    if ($missingManuals) {
        throw "Versioned user manuals were not found: $($missingManuals -join ', ')"
    }
    Copy-Item -LiteralPath $manuals -Destination $distDirectory -Force
    $manualDirectory = Join-Path $distDirectory "NEOMapper\manuals"
    New-Item -ItemType Directory -Path $manualDirectory -Force | Out-Null
    Copy-Item -LiteralPath $manuals -Destination $manualDirectory -Force
    $archive = Join-Path $repositoryRoot "dist\NEOMapper-Windows-x64.zip"
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
    Compress-Archive -Path "dist\NEOMapper\*" -DestinationPath $archive -CompressionLevel Optimal
    $innoCompiler = Get-Command iscc -ErrorAction SilentlyContinue
    if (-not $innoCompiler) {
        $userInnoCompiler = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $userInnoCompiler) {
            $innoCompiler = Get-Item -LiteralPath $userInnoCompiler
        }
    }
    if ($innoCompiler) {
        $innoCompilerPath = if ($innoCompiler.Source) { $innoCompiler.Source } else { $innoCompiler.FullName }
        & $innoCompilerPath "/DMyAppVersion=$version" "installer\NEOMapper.iss"
        if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed." }
    }
    else {
        Write-Warning "Inno Setup not found; the portable ZIP was built, but the installer was skipped."
    }

    $checksums = Get-ChildItem "dist" -File | Sort-Object Name | ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $($_.Name)"
    }
    Set-Content -LiteralPath "dist\SHA256SUMS.txt" -Value $checksums -Encoding ascii
    Write-Host "Release artifacts created in $repositoryRoot\dist"
}
finally {
    Pop-Location
}
