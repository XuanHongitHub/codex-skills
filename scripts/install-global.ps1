param(
  [string]$RepoRoot = "F:\Herd\Skills\codex-skills",
  [string]$CodexSkillsRoot = "$env:USERPROFILE\.codex\skills"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RepoRoot)) {
  throw "RepoRoot not found: $RepoRoot"
}

New-Item -ItemType Directory -Force -Path $CodexSkillsRoot | Out-Null

$skillDirs = Get-ChildItem -LiteralPath $RepoRoot -Directory |
  Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") }

foreach ($skill in $skillDirs) {
  $target = Join-Path $CodexSkillsRoot $skill.Name
  if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target
    if ($item.LinkType -eq "Junction") {
      Write-Host "skip (junction exists): $($skill.Name)"
      continue
    }
    Write-Host "skip (already exists, not junction): $($skill.Name)"
    continue
  }

  New-Item -ItemType Junction -Path $target -Target $skill.FullName | Out-Null
  Write-Host "linked: $($skill.Name)"
}

Write-Host "Done. Skills linked to $CodexSkillsRoot"
