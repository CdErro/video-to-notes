param(
    [switch]$Yes,
    [string]$Target = "conda:video-to-notes"
)

$scriptPath = Join-Path $PSScriptRoot "scripts\environment.py"
$arguments = @($scriptPath, "install", "--target", $Target)
if ($Yes) { $arguments += "--yes" }

if (Get-Command conda -ErrorAction SilentlyContinue) {
    & conda run -n base python @arguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @arguments
} else {
    Write-Error "Python 3.11+ or Conda is required to run setup."
    exit 1
}
exit $LASTEXITCODE
