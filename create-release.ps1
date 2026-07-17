# create-release.ps1 — commit, tag, push, and publish a GitHub release for Petal.
#
# Assumes the signed APK is already built (run .\build-release.ps1 first).
# Reads the version from pyproject.toml; prompts once for a message that becomes
# BOTH the git commit message and the release notes.
#
#   .\create-release.ps1
#   .\create-release.ps1 -Build     # build the signed APK first
#   .\create-release.ps1 -Force     # re-release an existing version

param(
    [switch]$Build,  # -Build to run build-release.ps1 first
    [switch]$Force   # -Force to re-release an existing version (re-points tag, replaces release)
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$Repo = "3th4n-J/petal-app"
$Apk  = Join-Path $PSScriptRoot "build\apk\Petal.apk"

# ── Version from pyproject.toml → tag like v3.1.0 ────────────────────────────
$m = Select-String -Path ".\pyproject.toml" -Pattern '^\s*version\s*=\s*"([^"]+)"' |
     Select-Object -First 1
if (-not $m) { throw "Couldn't read version from pyproject.toml." }
$Version = $m.Matches[0].Groups[1].Value
$Tag = "v$Version"

# ── Preconditions ────────────────────────────────────────────────────────────
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) not found on PATH. Install it, then run 'gh auth login'."
}
if ($Build) {
    Write-Host "Building signed APK first..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build-release.ps1")
    if ($LASTEXITCODE -ne 0) { throw "build-release.ps1 failed." }
}
if (-not (Test-Path $Apk)) {
    $found = Get-ChildItem ".\build\apk\*.apk" -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime | Select-Object -Last 1
    if ($found) { $Apk = $found.FullName }
    else { throw "APK not found at $Apk. Build it first (.\build-release.ps1)." }
}

# Duplicate-tag guard — usually means you forgot to bump the version.
git rev-parse -q --verify "refs/tags/$Tag" *> $null
$LocalTagExists = ($LASTEXITCODE -eq 0)
if ($LocalTagExists -and -not $Force) {
    throw "Tag $Tag already exists locally. Bump the version, or pass -Force to re-release it."
}

# ── Message (commit + release notes) ─────────────────────────────────────────
$Message = Read-Host "Release message for $Tag (commit + notes)"
if (-not $Message.Trim()) { throw "A release message is required." }

# ── Confirm ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("About to release:" + $(if ($Force) { "   [FORCE re-release]" } else { "" })) -ForegroundColor Cyan
Write-Host "  Tag:      $Tag"
Write-Host "  Repo:     $Repo"
Write-Host "  APK:      $Apk  ($([math]::Round((Get-Item $Apk).Length/1MB,1)) MB)"
Write-Host "  Message:  $Message"
if ((Read-Host "Proceed? (y/N)") -ne 'y') { Write-Host "Aborted."; return }

# ── Commit (skip cleanly if there's nothing to commit) ──────────────────────
if (git status --porcelain) {
    git add -A
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }
} else {
    Write-Host "No changes to commit — releasing current HEAD." -ForegroundColor Yellow
}

# ── Tag + push ───────────────────────────────────────────────────────────────
if ($LocalTagExists -and $Force) {
    git tag -d $Tag | Out-Null    # drop the stale local tag so we can re-point it
}
git tag $Tag;                 if ($LASTEXITCODE -ne 0) { throw "git tag failed." }
git push;                     if ($LASTEXITCODE -ne 0) { throw "git push failed." }
if ($Force) {
    git push origin $Tag --force; if ($LASTEXITCODE -ne 0) { throw "git push tag failed." }
} else {
    git push --tags;          if ($LASTEXITCODE -ne 0) { throw "git push --tags failed." }
}

# ── GitHub release ───────────────────────────────────────────────────────────
if ($Force) {
    gh release delete $Tag --repo $Repo --yes 2>$null
}
gh release create $Tag $Apk `
    --repo $Repo `
    --title "Petal $Tag" `
    --notes $Message
if ($LASTEXITCODE -ne 0) { throw "gh release create failed." }

Write-Host ""
Write-Host "Released $Tag -> https://github.com/$Repo/releases/tag/$Tag" -ForegroundColor Green
