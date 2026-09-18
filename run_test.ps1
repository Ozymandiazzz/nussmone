# Run the validated ccstudio.py pipeline against a GLB.
# Does not change pipeline logic.
#
#   .\run_test.ps1 -Input "objeto.glb" -Name "handle_object"

param(
    [Parameter(Mandatory = $true)]
    [string]$Input,

    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Template = "",

    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
)

$ErrorActionPreference = "Stop"

# $input is a reserved PowerShell enumerator; keep the -Input CLI name via bound params.
$inputPath = $PSBoundParameters["Input"]
$root = $PSScriptRoot
$ccstudio = Join-Path $root "ccstudio.py"
$outDir = Join-Path (Join-Path $root "output") $Name
$logPath = Join-Path $outDir "run.log"

if ([string]::IsNullOrWhiteSpace($Name) -or $Name -match '[\\/:]') {
    Write-Error "Name must be a simple folder name (no path separators)."
    exit 1
}

if (-not $Template) {
    $Template = Join-Path $root "fixtures\v0.1-vase\funcionasera.blend"
}

if (-not (Test-Path -LiteralPath $ccstudio)) {
    Write-Error "ccstudio.py not found: $ccstudio"
    exit 1
}
if (-not (Test-Path -LiteralPath $Blender)) {
    Write-Error "Blender 4.4.3 not found: $Blender"
    exit 1
}
if (-not (Test-Path -LiteralPath $inputPath)) {
    Write-Error "Input GLB not found: $inputPath"
    exit 1
}
if (-not (Test-Path -LiteralPath $Template)) {
    Write-Error "Template blend not found: $Template"
    exit 1
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$header = @(
    "CC Studio v0.1 runner"
    "started: $(Get-Date -Format o)"
    "blender: $Blender"
    "script:  $ccstudio"
    "input:   $((Resolve-Path -LiteralPath $inputPath).Path)"
    "template:$((Resolve-Path -LiteralPath $Template).Path)"
    "output:  $outDir"
    ""
)
Set-Content -LiteralPath $logPath -Value $header -Encoding UTF8

$blenderArgs = @(
    "--background",
    "--python", $ccstudio,
    "--",
    "--input", (Resolve-Path -LiteralPath $inputPath).Path,
    "--template", (Resolve-Path -LiteralPath $Template).Path,
    "--output", $outDir
)

& $Blender @blenderArgs 2>&1 | Tee-Object -FilePath $logPath -Append
$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) {
    $exitCode = 1
}

Add-Content -LiteralPath $logPath -Value ""
Add-Content -LiteralPath $logPath -Value "exit_code: $exitCode"
Add-Content -LiteralPath $logPath -Value "finished: $(Get-Date -Format o)"

exit $exitCode
