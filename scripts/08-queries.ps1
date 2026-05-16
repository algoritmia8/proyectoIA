$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$project = "Algoritmia IA"
$org = "https://algoritmia8.visualstudio.com"

function Invoke-Az($params) {
    & az @params
}

# Ensure folder "Grupo IA" exists under Shared Queries
function Ensure-Folder($name) {
    $tmp = New-TemporaryFile
    $json = @{ name = $name; isFolder = $true } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($tmp.FullName, $json, (New-Object System.Text.UTF8Encoding($false)))
    try {
        az devops invoke `
            --organization $org `
            --area wit `
            --resource queries `
            --route-parameters project="$project" query="Shared Queries" `
            --http-method POST `
            --api-version "7.0" `
            --in-file $tmp.FullName `
            -o none 2>$null
        Write-Host "Folder '$name' created (or already exists)"
    } catch {
        Write-Host "Folder '$name' may already exist"
    } finally {
        Remove-Item $tmp -Force
    }
}

function New-Query($name, $wiql) {
    $body = @{ name = $name; wiql = $wiql } | ConvertTo-Json -Compress
    $tmp = New-TemporaryFile
    [System.IO.File]::WriteAllText($tmp.FullName, $body, (New-Object System.Text.UTF8Encoding($false)))
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $null = az devops invoke `
            --organization $org `
            --area wit `
            --resource queries `
            --route-parameters project="$project" query="Shared Queries/Grupo IA" `
            --http-method POST `
            --api-version "7.0" `
            --in-file $tmp.FullName `
            -o none 2>&1
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            Write-Host "  + Query '$name' created"
        } else {
            $null = az devops invoke `
                --organization $org `
                --area wit `
                --resource queries `
                --route-parameters project="$project" query="Shared Queries/Grupo IA/$name" `
                --http-method PATCH `
                --api-version "7.0" `
                --in-file $tmp.FullName `
                -o none 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ~ Query '$name' updated"
            } else {
                Write-Host "  ! Query '$name' FAILED"
            }
        }
        $ErrorActionPreference = $prev
    } finally {
        Remove-Item $tmp -Force
    }
}

Ensure-Folder "Grupo IA"

$queries = @(
    @{
        name = "KPI Radar - pendientes"
        wiql = "SELECT [System.Id],[System.Title],[System.AreaPath],[System.IterationPath],[System.State],[System.AssignedTo],[System.Tags] FROM WorkItems WHERE [System.TeamProject]=@project AND [System.WorkItemType]='Requirement' AND [System.Tags] CONTAINS 'kpi-mensual' AND [System.Tags] CONTAINS 'radar' AND [System.State] <> '90 - Cerrado' ORDER BY [System.IterationPath],[System.AreaPath]"
    },
    @{
        name = "KPI Knowledge - pendientes"
        wiql = "SELECT [System.Id],[System.Title],[System.AreaPath],[System.IterationPath],[System.State],[System.AssignedTo],[System.Tags] FROM WorkItems WHERE [System.TeamProject]=@project AND [System.WorkItemType]='Requirement' AND [System.Tags] CONTAINS 'kpi-mensual' AND [System.Tags] CONTAINS 'knowledge' AND [System.State] <> '90 - Cerrado' ORDER BY [System.IterationPath],[System.AreaPath]"
    },
    @{
        name = "Backlog por Area"
        wiql = "SELECT [System.Id],[System.WorkItemType],[System.Title],[System.AreaPath],[System.State],[System.AssignedTo] FROM WorkItems WHERE [System.TeamProject]=@project AND [System.WorkItemType] IN ('Epic','Feature','Requirement','Task') AND [System.AreaPath] UNDER 'Algoritmia IA' ORDER BY [System.AreaPath],[System.WorkItemType],[System.Id]"
    },
    @{
        name = "Roadmap por Iteracion"
        wiql = "SELECT [System.Id],[System.WorkItemType],[System.Title],[System.IterationPath],[System.State],[System.AssignedTo] FROM WorkItems WHERE [System.TeamProject]=@project AND [System.IterationPath] UNDER 'Algoritmia IA\2026' ORDER BY [System.IterationPath],[System.WorkItemType],[System.Id]"
    },
    @{
        name = "Sprint-01 - Tareas"
        wiql = "SELECT [System.Id],[System.Title],[System.AreaPath],[System.State],[System.AssignedTo] FROM WorkItems WHERE [System.TeamProject]=@project AND [System.WorkItemType]='Task' AND [System.IterationPath]='Algoritmia IA\2026\Q2\Sprint-01' ORDER BY [System.AreaPath],[System.Id]"
    },
    @{
        name = "Items sin asignar"
        wiql = "SELECT [System.Id],[System.WorkItemType],[System.Title],[System.AreaPath],[System.Tags] FROM WorkItems WHERE [System.TeamProject]=@project AND [System.AssignedTo]='' AND [System.State] <> '90 - Cerrado' ORDER BY [System.WorkItemType],[System.AreaPath]"
    }
)

foreach ($q in $queries) {
    New-Query $q.name $q.wiql
}

Write-Host ""
Write-Host "=== Done ==="
