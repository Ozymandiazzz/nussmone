# CC Studio — product entrypoint (GLB -> Sims-ready blend)
#
#   .\ccstudio.ps1 -Input "caminho\objeto.glb"
#   .\ccstudio.ps1 -Input "objeto.glb" -RotateX 90
#
# Optional: -RotateX -RotateY -RotateZ (degrees, default 0)
# Optional: -Force to overwrite an existing output folder
# Optional: -Name "label" for a stable output folder name under output/
# Optional: -Blender / -Template to override auto-detection

param(
    [Parameter(Mandatory = $true)]
    [string]$Input,

    [double]$RotateX = 0,
    [double]$RotateY = 0,
    [double]$RotateZ = 0,

    [string]$Name = "",
    [string]$Template = "",
    [string]$Blender = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# -Input CLI name; $input is reserved in PowerShell.
$inputPath = $PSBoundParameters["Input"]
$root = $PSScriptRoot
$ccstudio = Join-Path $root "ccstudio.py"

function Write-Info([string]$msg) { Write-Host $msg }
function Write-Fail([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Write-Pass([string]$msg) { Write-Host "[PASS] $msg" -ForegroundColor Green }

function Find-Blender44 {
    $candidates = @(
        "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.4.3\blender.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    $base = "C:\Program Files\Blender Foundation"
    if (Test-Path -LiteralPath $base) {
        $dirs = Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Blender 4\.4' } |
            Sort-Object Name -Descending
        foreach ($d in $dirs) {
            $exe = Join-Path $d.FullName "blender.exe"
            if (Test-Path -LiteralPath $exe) { return $exe }
        }
    }
    return $null
}

function New-UniqueOutputName([string]$glbPath) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($glbPath)
    if ([string]::IsNullOrWhiteSpace($base)) { $base = "run" }
    $safe = ($base -replace '[^\w\-.]+', '_').Trim('_')
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = "run" }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    return "{0}_{1}" -f $safe, $stamp
}

function Confirm-Overwrite([string]$dir) {
    if (-not (Test-Path -LiteralPath $dir)) { return $true }
    if ($Force) {
        Write-Info "Overwriting existing output (-Force): $dir"
        Remove-Item -LiteralPath $dir -Recurse -Force
        return $true
    }
    if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
        $ans = Read-Host "Output folder already exists: $dir`nOverwrite? [y/N]"
        if ($ans -match '^[yY]') {
            Remove-Item -LiteralPath $dir -Recurse -Force
            return $true
        }
        return $false
    }
    Write-Fail "Output folder exists (pass -Force to overwrite): $dir"
    return $false
}

# --- resolve paths ---
if (-not (Test-Path -LiteralPath $ccstudio)) {
    Write-Fail "ccstudio.py not found next to this script: $ccstudio"
    exit 1
}

if (-not (Test-Path -LiteralPath $inputPath)) {
    Write-Fail "Input GLB not found: $inputPath"
    exit 1
}
$inputPath = (Resolve-Path -LiteralPath $inputPath).Path
Write-Info "Input:   $inputPath"

if ([string]::IsNullOrWhiteSpace($Blender)) {
    $Blender = Find-Blender44
}
if ([string]::IsNullOrWhiteSpace($Blender) -or -not (Test-Path -LiteralPath $Blender)) {
    Write-Fail "Blender 4.4.x not found. Install Blender 4.4 or pass -Blender."
    exit 1
}
$Blender = (Resolve-Path -LiteralPath $Blender).Path
Write-Info "Blender: $Blender"

if ([string]::IsNullOrWhiteSpace($Template)) {
    $templateCandidates = @(
        (Join-Path $root "templates\decor_vase\template.blend"),
        (Join-Path $root "fixtures\v0.1-vase\funcionasera.blend")
    )
    foreach ($c in $templateCandidates) {
        if (Test-Path -LiteralPath $c) {
            $Template = $c
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($Template) -or -not (Test-Path -LiteralPath $Template)) {
    Write-Fail "Validated template not found. Expected templates\decor_vase\template.blend"
    exit 1
}
$Template = (Resolve-Path -LiteralPath $Template).Path
Write-Info "Template: $Template"

if ([string]::IsNullOrWhiteSpace($Name)) {
    $Name = New-UniqueOutputName $inputPath
}
if ($Name -match '[\\/:]') {
    Write-Fail "Name must be a simple folder name (no path separators)."
    exit 1
}

$outDir = Join-Path (Join-Path $root "output") $Name
if (-not (Confirm-Overwrite $outDir)) {
    exit 1
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$logPath = Join-Path $outDir "run.log"
Write-Info "Output:  $outDir"
Write-Info "Processing..."

$header = @(
    "CC Studio product run"
    "started: $(Get-Date -Format o)"
    "blender: $Blender"
    "script:  $ccstudio"
    "input:   $inputPath"
    "template:$Template"
    "output:  $outDir"
    "rotate:  x=$RotateX y=$RotateY z=$RotateZ"
    ""
)
Set-Content -LiteralPath $logPath -Value $header -Encoding UTF8

$blenderArgs = @(
    "--background",
    "--python", $ccstudio,
    "--",
    "--input", $inputPath,
    "--template", $Template,
    "--output", $outDir,
    "--rotate-x", "$RotateX",
    "--rotate-y", "$RotateY",
    "--rotate-z", "$RotateZ"
)

# Full Blender console noise stays in run.log; terminal stays short.
& $Blender @blenderArgs *>> $logPath
$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) { $exitCode = 1 }

Add-Content -LiteralPath $logPath -Value ""
Add-Content -LiteralPath $logPath -Value "exit_code: $exitCode"
Add-Content -LiteralPath $logPath -Value "finished: $(Get-Date -Format o)"

$blendOut = Join-Path $outDir "sims_ready.blend"
$pngOut = Join-Path $outDir "basecolor.png"
$reportOut = Join-Path $outDir "report.json"

$status = $null
if (Test-Path -LiteralPath $reportOut) {
    try {
        $report = Get-Content -LiteralPath $reportOut -Raw -Encoding UTF8 | ConvertFrom-Json
        $status = $report.status
    } catch {
        $status = $null
    }
}

$ok = ($exitCode -eq 0) -and ($status -eq "success") `
    -and (Test-Path -LiteralPath $blendOut) `
    -and (Test-Path -LiteralPath $pngOut) `
    -and (Test-Path -LiteralPath $reportOut)

if ($ok) {
    Write-Pass "Pipeline finished."
    Write-Info "  sims_ready.blend  $blendOut"
    Write-Info "  basecolor.png     $pngOut"
    Write-Info "  report.json       $reportOut"
    Write-Info "  run.log           $logPath"
    exit 0
}

Write-Fail "Pipeline failed (exit=$exitCode status=$status)."
Write-Info "See log: $logPath"
if (Test-Path -LiteralPath $reportOut) {
    Write-Info "See report: $reportOut"
}
exit 1
