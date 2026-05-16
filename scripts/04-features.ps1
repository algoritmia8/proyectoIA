$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$cfg   = Get-Content .\scripts\features-config.json -Raw -Encoding UTF8 | ConvertFrom-Json
$epics = Get-Content .\scripts\epics.json           -Raw -Encoding UTF8 | ConvertFrom-Json

# Pre-fetch existing Features in project to avoid duplicates
Write-Host "Loading existing Features..."
$existingWiql = "SELECT [System.Id],[System.Title] FROM WorkItems WHERE [System.TeamProject]='Algoritmia IA' AND [System.WorkItemType]='Feature'"
$existingRaw = az boards query --wiql $existingWiql -o json | ConvertFrom-Json
$existing = @{}
foreach ($w in $existingRaw) { $existing[$w.fields.'System.Title'] = $w.id }
Write-Host ("Found {0} existing features." -f $existing.Count)

$out = @{}
$i = 0
foreach ($f in $cfg.features) {
    $i++
    $parentId = $epics.($f.epic)

    if ($existing.ContainsKey($f.title)) {
        $id = $existing[$f.title]
        Write-Host ("[{0}/{1}] SKIP existing '{2}' -> #{3}" -f $i, $cfg.features.Count, $f.title, $id)
        $key = ($f.title -replace '[^A-Za-z0-9]+','_').Trim('_')
        $out[$key] = $id
        continue
    }

    Write-Host ("[{0}/{1}] Creating Feature '{2}' (parent Epic #{3})" -f $i, $cfg.features.Count, $f.title, $parentId)

    $args = @(
        "boards","work-item","create",
        "--type","Feature",
        "--title", $f.title,
        "--area",  $f.area,
        "--iteration", $f.iter,
        "--description", $f.desc,
        "--fields", "System.Tags=$($f.tags)",
        "-o","json"
    )
    if ($f.assignee) { $args += @("--assigned-to", $f.assignee) }

    $json = & az @args 2>$null
    if (-not $json) { Write-Warning "Failed to create $($f.title)"; continue }
    $wi = $json | ConvertFrom-Json
    $id = $wi.id

    # Link to parent epic
    & az boards work-item relation add --id $id --relation-type "Parent" --target-id $parentId -o none 2>$null | Out-Null

    $key = ($f.title -replace '[^A-Za-z0-9]+','_').Trim('_')
    $out[$key] = $id
    Write-Host ("  -> Feature #{0}" -f $id)
}

$out | ConvertTo-Json -Depth 4 | Out-File -FilePath .\scripts\features.json -Encoding UTF8
Write-Host ""
Write-Host "=== Features IDs saved to scripts\features.json ==="
$out.GetEnumerator() | Sort-Object Name | Format-Table -AutoSize
