param(
    [string]$PostgresDb = "schedule_optimizer",
    [string]$PostgresUser = "postgres",
    [string]$PostgresPassword = "",
    [string]$PostgresHost = "127.0.0.1",
    [string]$PostgresPort = "5432",
    [switch]$SkipFullDump = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [string]$Exe,
        [string[]]$Args
    )

    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Exe $($Args -join ' ')"
    }
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DjangoRoot = Join-Path $ProjectRoot "schedule_optimizer"
$ManagePy = Join-Path $DjangoRoot "manage.py"
$SqliteDb = Join-Path $DjangoRoot "db.sqlite3"

$PythonCandidates = @(
    (Join-Path $DjangoRoot "venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot "venv\Scripts\python.exe"),
    "py"
)

$PythonExe = $null
foreach ($candidate in $PythonCandidates) {
    if ($candidate -eq "py") {
        $PythonExe = "py"
        break
    }
    if (Test-Path -LiteralPath $candidate) {
        $PythonExe = $candidate
        break
    }
}

if (-not $PythonExe) {
    throw "Python executable not found."
}

if (-not (Test-Path -LiteralPath $ManagePy)) {
    throw "manage.py not found: $ManagePy"
}

if (-not (Test-Path -LiteralPath $SqliteDb)) {
    throw "SQLite database not found: $SqliteDb"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups"
$BackupDir = Join-Path $BackupRoot "sqlite_to_postgres_$timestamp"
$null = New-Item -ItemType Directory -Path $BackupDir -Force

$sqliteBackup = Join-Path $BackupDir "db.sqlite3.backup"
Copy-Item -LiteralPath $SqliteDb -Destination $sqliteBackup -Force

$mediaDir = Join-Path $DjangoRoot "media"
if (Test-Path -LiteralPath $mediaDir) {
    $mediaItems = Get-ChildItem -LiteralPath $mediaDir -Force -ErrorAction SilentlyContinue
    if ($mediaItems) {
        $mediaBackup = Join-Path $BackupDir "media_backup.zip"
        Compress-Archive -Path (Join-Path $mediaDir "*") -DestinationPath $mediaBackup -Force
    }
}

$fullDumpPath = Join-Path $BackupDir "full_dump.json"
$safeDumpPath = Join-Path $BackupDir "safe_dump.json"

Push-Location $DjangoRoot
try {
    Write-Host "[1/6] Creating JSON dumps from SQLite..."
    $env:USE_POSTGRES = "0"
    Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_USER -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_HOST -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_PORT -ErrorAction SilentlyContinue

    if (-not $SkipFullDump) {
        if ($PythonExe -eq "py") {
            Invoke-CheckedCommand -Exe $PythonExe -Args @("-3", "manage.py", "dumpdata", "--indent", "2", "--output", $fullDumpPath)
        } else {
            Invoke-CheckedCommand -Exe $PythonExe -Args @("manage.py", "dumpdata", "--indent", "2", "--output", $fullDumpPath)
        }
    }

    $safeDumpArgs = @(
        "manage.py", "dumpdata",
        "--exclude", "auth.permission",
        "--exclude", "contenttypes",
        "--exclude", "admin.logentry",
        "--exclude", "sessions",
        "--natural-foreign",
        "--natural-primary",
        "--indent", "2",
        "--output", $safeDumpPath
    )
    if ($PythonExe -eq "py") {
        Invoke-CheckedCommand -Exe $PythonExe -Args (@("-3") + $safeDumpArgs)
    } else {
        Invoke-CheckedCommand -Exe $PythonExe -Args $safeDumpArgs
    }

    Write-Host "[2/6] Switching environment to PostgreSQL..."
    $env:USE_POSTGRES = "1"
    $env:POSTGRES_DB = $PostgresDb
    $env:POSTGRES_USER = $PostgresUser
    $env:POSTGRES_PASSWORD = $PostgresPassword
    $env:POSTGRES_HOST = $PostgresHost
    $env:POSTGRES_PORT = $PostgresPort

    Write-Host "[3/6] Applying migrations on PostgreSQL..."
    if ($PythonExe -eq "py") {
        Invoke-CheckedCommand -Exe $PythonExe -Args @("-3", "manage.py", "migrate")
    } else {
        Invoke-CheckedCommand -Exe $PythonExe -Args @("manage.py", "migrate")
    }

    Write-Host "[4/6] Loading transferred data into PostgreSQL..."
    if ($PythonExe -eq "py") {
        Invoke-CheckedCommand -Exe $PythonExe -Args @("-3", "manage.py", "loaddata", $safeDumpPath)
    } else {
        Invoke-CheckedCommand -Exe $PythonExe -Args @("manage.py", "loaddata", $safeDumpPath)
    }

    Write-Host "[5/6] Running post-migration count checks..."
    $checkScript = @"
from django.contrib.auth.models import User
from core.models import UserProfile, Employee, Schedule, ShiftAssignment, TimeOffRequest, ShiftSwapRequest, ChatConversation, ChatMessage
models = [
    ("auth_user", User),
    ("core_userprofile", UserProfile),
    ("core_employee", Employee),
    ("core_schedule", Schedule),
    ("core_shiftassignment", ShiftAssignment),
    ("core_timeoffrequest", TimeOffRequest),
    ("core_shiftswaprequest", ShiftSwapRequest),
    ("core_chatconversation", ChatConversation),
    ("core_chatmessage", ChatMessage),
]
for name, model in models:
    print(f"{name}: {model.objects.count()}")
"@
    if ($PythonExe -eq "py") {
        Invoke-CheckedCommand -Exe $PythonExe -Args @("-3", "manage.py", "shell", "-c", $checkScript)
    } else {
        Invoke-CheckedCommand -Exe $PythonExe -Args @("manage.py", "shell", "-c", $checkScript)
    }

    Write-Host "[6/6] Done."
    Write-Host "Backup folder: $BackupDir"
    Write-Host "To keep PostgreSQL active, set:"
    Write-Host "  USE_POSTGRES=1"
    Write-Host "  POSTGRES_DB=$PostgresDb"
    Write-Host "  POSTGRES_USER=$PostgresUser"
    Write-Host "  POSTGRES_PASSWORD=<your_password>"
    Write-Host "  POSTGRES_HOST=$PostgresHost"
    Write-Host "  POSTGRES_PORT=$PostgresPort"
}
finally {
    Pop-Location
}
