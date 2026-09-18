param([string]$AdminEmail = 'admin@basketvision.local', [string]$DemoEmail = 'demo@basketvision.local')
$ErrorActionPreference = 'Stop'
$target = Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
if (Test-Path -LiteralPath $target) { throw '.env already exists. Configure it manually; existing credentials were not changed.' }
function New-Secret {
    $bytes = New-Object byte[] 48
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes)
}
$content = @(
    'AUTH_SIGNING_KEY=' + (New-Secret)
    'AUTH_SECURE_COOKIES=false'
    'SEED_ADMIN_EMAIL=' + $AdminEmail
    'SEED_ADMIN_PASSWORD=Aa1!' + (New-Secret)
    'SEED_DEMO_EMAIL=' + $DemoEmail
    'SEED_DEMO_PASSWORD=Aa1!' + (New-Secret)
)
[IO.File]::WriteAllLines($target, $content)
Write-Output 'Created local .env with random credentials. Open the file locally to sign in; do not share it.'
