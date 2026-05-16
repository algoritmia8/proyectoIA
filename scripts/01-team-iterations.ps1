$ErrorActionPreference = "Stop"
$proj = "Algoritmia IA"
$team = "Algoritmia IA Team"
$sprint01 = "d150412d-b6b5-4613-92d8-7f97f3ff530d"

$root = az boards iteration project list --project $proj --path "\Algoritmia IA\Iteration\2026" --depth 0 --query "identifier" -o tsv
Write-Host "Root 2026 id: $root"

az boards iteration team set-default-iteration --id $sprint01 --team $team --project $proj -o none
az boards iteration team set-backlog-iteration --id $root --team $team --project $proj -o none
Write-Host "Default and backlog set"

foreach ($n in @("Iteration 0","Iteration 1","Iteration 2")) {
    $id = az boards iteration project show --path "\Algoritmia IA\Iteration\$n" --project $proj --query "identifier" -o tsv 2>$null
    if ($id) {
        az boards iteration team remove --id $id --team $team --project $proj -o none 2>$null
        Write-Host "Removed from team: $n"
    }
}

Write-Host "---ITER LIST---"
az boards iteration team list --team $team --project $proj --query "[].name" -o tsv
Write-Host "---DEFAULT---"
az boards iteration team show-default-iteration --team $team --project $proj --query "name" -o tsv
Write-Host "---BACKLOG---"
az boards iteration team show-backlog-iteration --team $team --project $proj --query "name" -o tsv
