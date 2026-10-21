# F3 of the contrastive CodeNet experiment: configurations A (no Wrong Answer negatives) and B (with them),
# 2 seeds each, all eligible problems, 3 epochs (150 000 triplets), CodeNet val only (no ESCOM numbers).
# Each run resumes from its own state.pt and is skipped once its result.json exists, so this script can be
# started again after any interruption. Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/run_f3.ps1
param(
    [string]$Out = "C:\Users\edani\datasets\codenet\f3",
    [int]$Triplets = 150000,
    [int]$ValEvery = 1000
)

$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force $Out | Out-Null
# B first for both seeds' counterparts to land early: B_s0, A_s0, B_s1, A_s1
$runs = @(
    @{ name = "B_s0"; seed = 0; extra = @() },
    @{ name = "A_s0"; seed = 0; extra = @("--no-wa") },
    @{ name = "B_s1"; seed = 1; extra = @() },
    @{ name = "A_s1"; seed = 1; extra = @("--no-wa") }
)
foreach ($r in $runs) {
    $dir = Join-Path $Out $r.name
    if (Test-Path (Join-Path $dir "result.json")) { "$($r.name): done, skipped"; continue }
    "$(Get-Date -Format s) start $($r.name)"
    $argv = @("scripts/contrastive_train.py", "train", "--out", $dir, "--problems", "0", "--triplets", $Triplets,
        "--pairs", "16", "--seed", $r.seed, "--val-every", $ValEvery, "--skip-escom") + $r.extra
    & python @argv *>> (Join-Path $Out "$($r.name).log")
    "$(Get-Date -Format s) end $($r.name) exit=$LASTEXITCODE"
}
"$(Get-Date -Format s) all runs finished"
