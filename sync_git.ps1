<#
.SYNOPSIS
    Automated GitHub synchronization script for PassKhadam.
.DESCRIPTION
    Stages all modified and new project files, commits with authenticated GitHub
    identity, and pushes to origin main. Supports one-shot sync or continuous background watching.
.PARAMETER Message
    Custom commit message. Defaults to timestamped description.
.PARAMETER Watch
    If specified, continuously watches the directory and pushes changes automatically.
#>
param(
    [string]$Message = "",
    [switch]$Watch
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RepoRoot

# Ensure Git author identity is compliant with GitHub email privacy
git config user.name "Mohammed Uzair"
git config user.email "iamuzzi-7523@users.noreply.github.com"

function Invoke-GitSync {
    param([string]$CommitMessage)
    
    if (-not $CommitMessage) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $CommitMessage = "Auto-sync PassKhadam system development - $timestamp"
    }

    Write-Host "`n=====================================================================" -ForegroundColor Cyan
    Write-Host " PASSKHADAM — GitHub Repository Synchronization" -ForegroundColor Cyan
    Write-Host "=====================================================================`n" -ForegroundColor Cyan

    $status = git status --short
    if (-not $status) {
        Write-Host "[INFO] Repository clean. No uncommitted changes detected." -ForegroundColor Yellow
        return
    }

    Write-Host "[1/4] Uncommitted modifications:" -ForegroundColor Green
    git status --short

    Write-Host "`n[2/4] Staging files..." -ForegroundColor Green
    git add -A

    Write-Host "`n[3/4] Committing: '$CommitMessage'..." -ForegroundColor Green
    git commit -m $CommitMessage

    Write-Host "`n[4/4] Pushing to origin main..." -ForegroundColor Green
    git push origin main

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[SUCCESS] Successfully pushed all updates to GitHub origin main!`n" -ForegroundColor Green
    } else {
        Write-Host "`n[ERROR] Git push failed with exit code $LASTEXITCODE" -ForegroundColor Red
    }
}

if ($Watch) {
    Write-Host "Starting PassKhadam Auto-Sync Watcher mode... (Press Ctrl+C to stop)" -ForegroundColor Cyan
    while ($true) {
        $status = git status --short
        if ($status) {
            Invoke-GitSync -CommitMessage "Auto-sync file changes - $(Get-Date -Format 'HH:mm:ss')"
        }
        Start-Sleep -Seconds 30
    }
} else {
    Invoke-GitSync -CommitMessage $Message
}
