param(
    [switch]$Yes,
    [string]$Target = ""
)

$scriptPath = Join-Path $PSScriptRoot "scripts\environment.py"
if (Get-Command conda -ErrorAction SilentlyContinue) {
    if (-not $Target) { $Target = "conda:video-to-notes" }
    $arguments = @($scriptPath, "install", "--target", $Target)
    if ($Yes) { $arguments += "--yes" }
    & conda run -n base python @arguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    if (-not $Target) { $Target = "venv:.venv" }
    $arguments = @($scriptPath, "install", "--target", $Target)
    if ($Yes) { $arguments += "--yes" }
    & python @arguments
} else {
    Write-Error "Python 3.11+ or Conda is required to run setup."
    exit 1
}
exit $LASTEXITCODE
