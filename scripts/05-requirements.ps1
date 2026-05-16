$ErrorActionPreference = "Stop"
$proj = "Algoritmia IA"
$features  = Get-Content .\scripts\features.json   -Raw -Encoding UTF8 | ConvertFrom-Json

$sp01 = "Algoritmia IA\2026\Q2\Sprint-01"
$sp02 = "Algoritmia IA\2026\Q2\Sprint-02"
$sp03 = "Algoritmia IA\2026\Q2\Sprint-03"

# Areas (key, displayName, areaPath, assignee, radarFeatureKey, knowledgeFeatureKey)
$pos = @(
  @{ key="coord"; name="Coordinacion";        area="Algoritmia IA\Coordinaci$([char]0xF3)n"; user="ifont@algoritmia8.com";    radar=$null;                              know=$null; isCoord=$true },
  @{ key="ce";    name="Customer Engagement"; area="Algoritmia IA\Customer Engagement";       user="martero@algoritmia8.com"; radar="Radar_Customer_Engagement";        know="Knowledge_Customer_Engagement" },
  @{ key="bc";    name="Business Central";    area="Algoritmia IA\Business Central";          user="lflorido@algoritmia8.com";radar="Radar_Business_Central";           know="Knowledge_Business_Central" },
  @{ key="fin";   name="Finance";             area="Algoritmia IA\Finance";                   user="ofolques@algoritmia8.com";radar="Radar_Finance";                    know="Knowledge_Finance" },
  @{ key="scm";   name="SCM";                 area="Algoritmia IA\SCM";                       user=$null;                     radar="Radar_SCM";                        know="Knowledge_SCM"; pendiente=$true },
  @{ key="ppfin"; name="Prog. Finance-PP";    area="Algoritmia IA\Prog. Finance-PP";          user="asalas@algoritmia8.com";  radar="Radar_Programacion_Finance_PP";    know="Knowledge_Programacion_Finance_PP" },
  @{ key="ppweb"; name="Prog. Web-Data";      area="Algoritmia IA\Prog. Web-Data";            user="promero@algoritmia8.com"; radar="Radar_Programacion_Web_Data";      know="Knowledge_Programacion_Web_Data" },
  @{ key="azure"; name="Azure";               area="Algoritmia IA\Azure";                     user="cgelonch@algoritmia8.com";radar="Radar_Azure";                      know="Knowledge_Azure" }
)

$altaId    = $features.Alta_y_onboarding_en_ALBA          # 13829
$reportId  = $features.Comunicacion_y_reporting_mensual   # 13832
$labId     = $features.Backlog_de_experimentos_del_Lab    # 13855

# Existing requirements (skip duplicates)
Write-Host "Loading existing Requirements..."
$wiql = "SELECT [System.Id],[System.Title] FROM WorkItems WHERE [System.TeamProject]='$proj' AND [System.WorkItemType]='Requirement'"
$existingRaw = az boards query --wiql $wiql -o json | ConvertFrom-Json
$existing = @{}
foreach ($w in $existingRaw) { $existing[$w.fields.'System.Title'] = $w.id }
Write-Host ("Found {0} existing requirements." -f $existing.Count)

$out = @{}

function New-Req {
  param($title, $area, $iter, $assignee, $tags, $parentId, $desc)

  if ($existing.ContainsKey($title)) {
    $id = $existing[$title]
    Write-Host "  SKIP existing '$title' -> #$id"
    return $id
  }

  $args = @(
    "boards","work-item","create",
    "--project",$proj,
    "--type","Requirement",
    "--title",$title,
    "--area",$area,
    "--iteration",$iter,
    "--fields","System.Tags=$tags","Microsoft.VSTS.Common.Priority=2"
  )
  if ($assignee) { $args += @("--assigned-to",$assignee) }
  if ($desc) { $args += @("--description",$desc) }

  $json = az @args -o json 2>$null
  $w = $json | ConvertFrom-Json
  $id = $w.id
  Write-Host "  -> Requirement #$id : $title"
  az boards work-item relation add --id $id --relation-type "Parent" --target-id $parentId -o none 2>$null | Out-Null
  return $id
}

$total = 0
foreach ($po in $pos) {
  $name = $po.name
  Write-Host ""
  Write-Host "=== $name ==="
  $tags = "arranque"
  if ($po.pendiente) { $tags = "$tags; po-pendiente" }
  $descSCM = if ($po.pendiente) { "PO pendiente de incorporar en DevOps (Dani Gaya). Asignar cuando esté disponible." } else { $null }

  # Sprint-01: Onboarding ALBA (todos)
  $t = "Configurar acceso ALBA y explorar Radar/Knowledge - $name"
  $id = New-Req $t $po.area $sp01 $po.user $tags $altaId $descSCM
  $out[$t] = $id; $total++

  if (-not $po.isCoord) {
    # Sprint-01: Primera aportacion al Radar
    $t = "Primera aportacion al Radar - $name"
    $parent = $features.($po.radar)
    $id = New-Req $t $po.area $sp01 $po.user ("radar; arranque" + $(if($po.pendiente){"; po-pendiente"})) $parent $descSCM
    $out[$t] = $id; $total++

    # Sprint-02: Primer articulo Knowledge
    $t = "Primer articulo en Knowledge - $name"
    $parent = $features.($po.know)
    $id = New-Req $t $po.area $sp02 $po.user ("knowledge; arranque" + $(if($po.pendiente){"; po-pendiente"})) $parent $descSCM
    $out[$t] = $id; $total++

    # Sprint-03: Backlog experimentos
    $t = "Definir backlog de experimentos del area - $name"
    $id = New-Req $t $po.area $sp03 $po.user ("lab; arranque" + $(if($po.pendiente){"; po-pendiente"})) $labId $descSCM
    $out[$t] = $id; $total++
  }

  # Reporte mensual recurrente (Sprint-01 como primera instancia)
  $t = "Reporte mensual a Coordinacion - $name"
  $id = New-Req $t $po.area $sp01 $po.user ("recurrente; arranque" + $(if($po.pendiente){"; po-pendiente"})) $reportId $descSCM
  $out[$t] = $id; $total++
}

Write-Host ""
Write-Host "=== $total Requirements processed. Saving... ==="
$out | ConvertTo-Json | Out-File .\scripts\requirements.json -Encoding UTF8
$out
