$ErrorActionPreference = "Stop"
$proj = "Algoritmia IA"

function New-Epic([string]$title, [string]$area, [string]$iter, [string]$assignee, [string]$tags, [string]$desc) {
    $args = @(
        "boards", "work-item", "create",
        "--project", $proj,
        "--type", "Epic",
        "--title", $title,
        "--area", $area,
        "--iteration", $iter,
        "--description", $desc,
        "--fields", "System.Tags=$tags",
        "-o", "json"
    )
    if ($assignee) { $args += @("--assigned-to", $assignee) }
    $json = & az @args | ConvertFrom-Json
    Write-Host "Created Epic $($json.id): $title"
    return $json.id
}

# 1) Repurpose #13816 → Arranque y Gobierno
Write-Host "=== Updating Epic #13816 → Arranque y Gobierno ==="
az boards work-item update --id 13816 `
    --title "🚀 Arranque y Gobierno" `
    --area "Algoritmia IA\Coordinación" `
    --iteration "Algoritmia IA\2026\Q2\Sprint-01" `
    --assigned-to "ifont@algoritmia8.com" `
    --description "Epic transversal de gobierno del Grupo de IA: operativa, accesos a ALBA, RBAC, KPIs, licencias Copilot y reuniones de seguimiento mensuales. Re-aprovecha la antigua Epic 'Diagnóstico y Estrategia' con foco en el arranque del grupo." `
    --fields "System.Tags=arranque; gobierno" `
    -o none
Write-Host "Updated #13816"

# 2) Close #13817–#13820 as Removed
foreach ($id in 13817..13820) {
    Write-Host "Closing #$id"
    az boards work-item update --id $id `
        --state "Closed" `
        --discussion "Reestructurada en líneas de actuación del nuevo plan del Grupo de IA. Epic cerrada como parte de la reorganización." `
        --fields "System.Tags=obsoleto" `
        -o none 2>&1 | Out-Null
}

# 3) Create 6 new line-of-action Epics
$epics = @{}
$epics["arranque"]   = 13816
$epics["vigilancia"] = New-Epic "📡 Vigilancia Tecnológica" "Algoritmia IA\Coordinación" "Algoritmia IA\2026" "ifont@algoritmia8.com" "radar; vigilancia" "Radar tecnológico por área: cada PO aporta de forma continua ítems al módulo Radar de ALBA. KPI: ≥2 ítems/mes por área."
$epics["knowledge"]  = New-Epic "📚 Base de Conocimiento" "Algoritmia IA\Coordinación" "Algoritmia IA\2026" "ifont@algoritmia8.com" "knowledge" "Base de Conocimiento del Grupo: artículos publicados por cada PO en Knowledge de ALBA. KPI: ≥1 artículo/mes por área."
$epics["formacion"]  = New-Epic "🎓 Formación Interna" "Algoritmia IA\Coordinación" "Algoritmia IA\2026\Q2" "rplana@algoritmia8.com" "guild; formacion" "Academy + Guild + formación interna IA. Incluye team building/evento de verano y calendario de Guild."
$epics["lab"]        = New-Epic "🧪 Laboratorio de Innovación" "Algoritmia IA\Coordinación" "Algoritmia IA\2026\Q3" "ifont@algoritmia8.com" "lab" "Lab del Grupo de IA: experimentos validados por área con plantilla común. Arranca en Q3."
$epics["portfolio"]  = New-Epic "💼 Portfolio de Soluciones" "Algoritmia IA\Coordinación" "Algoritmia IA\2026\Q4" "rplana@algoritmia8.com" "solutions; portfolio" "Catálogo de soluciones IA listas para venta a cliente. Objetivo: catálogo Q4."
$epics["soporte"]    = New-Epic "🤝 Soporte al Equipo" "Algoritmia IA\Coordinación" "Algoritmia IA\2026" "ifont@algoritmia8.com" "soporte" "Asistente IA interno + soporte transversal al equipo (resolución dudas, on-call ligero, documentación viva)."

$epics | ConvertTo-Json | Out-File -FilePath ".\scripts\epics.json" -Encoding utf8
Write-Host "`n=== Epics IDs ==="
$epics | Format-Table
