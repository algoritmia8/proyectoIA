$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$org     = "https://algoritmia8.visualstudio.com"
$project = "Algoritmia IA"
$team    = "98ffadb1-c96a-4fdd-b2cb-c10d310d968f"

# Query IDs (from Shared Queries/Grupo IA)
$qRadar      = "91ee2854-260f-40ba-8665-3d64ed4cf030"
$qKnowledge  = "3d0efcc1-20ea-4233-96d7-9cc8d2bcd62b"
$qBacklog    = "fceb007d-4d3f-4497-92b2-95bc1a92bf71"
$qRoadmap    = "737b26fe-e451-4ea0-96a3-1f6c564bcd6e"
$qSprint     = "196cf828-3e35-4eb5-84c5-50ee5dc522cc"
$qUnassigned = "da523e31-0e36-43e1-9533-3e188390c7d8"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Json($obj) {
    $tmp = New-TemporaryFile
    $json = $obj | ConvertTo-Json -Compress -Depth 10
    [System.IO.File]::WriteAllText($tmp.FullName, $json, $utf8NoBom)
    return $tmp.FullName
}

# 1) Create dashboard
$dashBody = @{
    name            = "Grupo IA - Seguimiento"
    description     = "Seguimiento global del Grupo IA: KPIs mensuales, backlog y roadmap"
    refreshInterval = 0
}
$tmp = Write-Json $dashBody
Write-Host "Creating dashboard..."
$resp = az devops invoke `
    --organization $org `
    --area dashboard `
    --resource dashboards `
    --route-parameters project="$project" team="$team" `
    --http-method POST `
    --api-version "7.0-preview" `
    --in-file $tmp `
    -o json 2>&1
Remove-Item $tmp -Force

if ($LASTEXITCODE -ne 0) {
    Write-Host "Dashboard create failed; trying to find existing..."
    $list = az devops invoke `
        --organization $org `
        --area dashboard `
        --resource dashboards `
        --route-parameters project="$project" team="$team" `
        --http-method GET `
        --api-version "7.0-preview" `
        -o json 2>$null | ConvertFrom-Json
    $dash = $list.value | Where-Object { $_.name -eq "Grupo IA - Seguimiento" } | Select-Object -First 1
    if (-not $dash) { Write-Host "ERROR: could not create or find dashboard"; exit 1 }
    $dashId = $dash.id
} else {
    $dashId = ($resp | ConvertFrom-Json).id
}
Write-Host "Dashboard id: $dashId"

# 2) Widgets - Query Scalar (count tile) + Query results widget
function Add-Widget($name, $queryId, $row, $col, $rowSpan, $colSpan, $contribId, $extraSettings) {
    $settings = @{ queryId = $queryId; queryName = $name } + $extraSettings
    $settingsJson = ($settings | ConvertTo-Json -Compress -Depth 10)
    $body = @{
        name            = $name
        position        = @{ row = $row; column = $col }
        size            = @{ rowSpan = $rowSpan; columnSpan = $colSpan }
        contributionId  = $contribId
        settings        = $settingsJson
        settingsVersion = @{ major = 1; minor = 0; patch = 0 }
    }
    $tmp = Write-Json $body
    $null = az devops invoke `
        --organization $org `
        --area dashboard `
        --resource widgets `
        --route-parameters project="$project" team="$team" dashboardId=$dashId `
        --http-method POST `
        --api-version "7.0-preview" `
        --in-file $tmp `
        -o none 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "  + Widget '$name'" }
    else { Write-Host "  ! Widget '$name' FAILED" }
    Remove-Item $tmp -Force
}

$scalar = "ms.vss-dashboards-web.Microsoft.VisualStudioOnline.Dashboards.QueryScalarWidget"
$results = "ms.vss-dashboards-web.Microsoft.VisualStudioOnline.Dashboards.QueryResultsWidget"

# Row 1: 4 scalar tiles
Add-Widget "KPI Radar pendientes"     $qRadar      1 1 1 1 $scalar @{}
Add-Widget "KPI Knowledge pendientes" $qKnowledge  1 2 1 1 $scalar @{}
Add-Widget "Items sin asignar"        $qUnassigned 1 3 1 1 $scalar @{}
Add-Widget "Sprint-01 - Tareas (n)"   $qSprint     1 4 1 1 $scalar @{}

# Row 2: scalar tiles for backlog/roadmap counts
Add-Widget "Backlog por Area"      $qBacklog 2 1 1 1 $scalar @{}
Add-Widget "Roadmap por Iteracion" $qRoadmap 2 2 1 1 $scalar @{}

Write-Host ""
Write-Host "=== Dashboard ready ==="
Write-Host "URL: $org/$([System.Uri]::EscapeDataString($project))/_dashboards/dashboard/$dashId"
