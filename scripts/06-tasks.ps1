$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$proj = 'Algoritmia IA'

# Load Requirements
$reqs = Get-Content .\scripts\requirements.json -Raw -Encoding UTF8 | ConvertFrom-Json
$reqMap = @{}
foreach ($p in $reqs.PSObject.Properties) { $reqMap[$p.Name] = $p.Value }

# Build a helper map: title -> id (titles are ASCII, no encoding issues)
function Get-ReqId([string]$title) { return $reqMap[$title] }

# POs: name, area, assignedTo
$pos = @(
  @{ name='Coordinacion';       area='Algoritmia IA\Coordinaci' + [char]0xF3 + 'n'; ass='ifont@algoritmia8.com';     hasArea=$false },
  @{ name='Customer Engagement';area='Algoritmia IA\Customer Engagement';            ass='martero@algoritmia8.com';   hasArea=$true  },
  @{ name='Business Central';   area='Algoritmia IA\Business Central';               ass='lflorido@algoritmia8.com';  hasArea=$true  },
  @{ name='Finance';            area='Algoritmia IA\Finance';                        ass='ofolques@algoritmia8.com';  hasArea=$true  },
  @{ name='SCM';                area='Algoritmia IA\SCM';                            ass=$null;                        hasArea=$true  },
  @{ name='Prog. Finance-PP';   area='Algoritmia IA\Prog. Finance-PP';               ass='asalas@algoritmia8.com';    hasArea=$true  },
  @{ name='Prog. Web-Data';     area='Algoritmia IA\Prog. Web-Data';                 ass='promero@algoritmia8.com';   hasArea=$true  },
  @{ name='Azure';              area='Algoritmia IA\Azure';                          ass='cgelonch@algoritmia8.com';  hasArea=$true  }
)

# Pre-load existing Tasks
Write-Host 'Loading existing Tasks...'
$wiql = "SELECT [System.Id],[System.Title] FROM WorkItems WHERE [System.TeamProject]='Algoritmia IA' AND [System.WorkItemType]='Task'"
$existing = az boards query --wiql $wiql -o json | ConvertFrom-Json
$taskMap = @{}
foreach ($e in $existing) { $taskMap[$e.fields.'System.Title'] = $e.id }
Write-Host ("Found {0} existing tasks." -f $taskMap.Count)

function New-Task([string]$title, [string]$area, [string]$iter, [string]$assigned, [int]$parentId, [string[]]$tags) {
  if ($taskMap.ContainsKey($title)) {
    Write-Host ("  SKIP existing Task '{0}' -> #{1}" -f $title, $taskMap[$title])
    return $taskMap[$title]
  }
  $args = @('boards','work-item','create','--project',$proj,'--type','Task','--title',$title,'--area',$area,'--iteration',$iter)
  if ($assigned) { $args += @('--assigned-to',$assigned) }
  if ($tags -and $tags.Count -gt 0) { $args += @('--fields', ('System.Tags=' + ($tags -join '; '))) }
  $args += @('-o','json')
  $json = & az @args 2>$null
  if (-not $json) { Write-Host ("  FAILED to create '{0}'" -f $title) -ForegroundColor Red; return $null }
  $w = $json | ConvertFrom-Json
  $id = $w.id
  az boards work-item relation add --id $id --relation-type Parent --target-id $parentId -o none 2>$null | Out-Null
  Write-Host ("  -> Task #{0} : {1}" -f $id, $title)
  $taskMap[$title] = $id
  return $id
}

$out = @{}

foreach ($po in $pos) {
  Write-Host ("`n=== {0} ===" -f $po.name)
  $area = $po.area
  $ass  = $po.ass
  $tagsPo = @('arranque')
  if (-not $ass) { $tagsPo += 'po-pendiente' }

  # 1) ALBA req (Sprint-01)
  $albaTitle = "Configurar acceso ALBA y explorar Radar/Knowledge - $($po.name)"
  $albaId = Get-ReqId $albaTitle
  if ($albaId) {
    $iter = 'Algoritmia IA\2026\Q2\Sprint-01'
    $t1 = New-Task "Alta de usuario en ALBA - $($po.name)"            $area $iter $ass $albaId ($tagsPo + 'alba')
    $t2 = New-Task "Lectura del Plan de Negocio IA - $($po.name)"     $area $iter $ass $albaId ($tagsPo + 'onboarding')
    $t3 = New-Task "Asistir kickoff Grupo IA - $($po.name)"           $area $iter $ass $albaId ($tagsPo + 'kickoff')
    $out["alba-$($po.name)"] = @{ req=$albaId; tasks=@($t1,$t2,$t3) }
  }

  # 2) Radar req (Sprint-01) — only for areas (not Coordinacion)
  if ($po.hasArea) {
    $radarTitle = "Primera aportacion al Radar - $($po.name)"
    $radarId = Get-ReqId $radarTitle
    if ($radarId) {
      $iter = 'Algoritmia IA\2026\Q2\Sprint-01'
      $t1 = New-Task "Identificar 1 novedad IA del area - $($po.name)" $area $iter $ass $radarId ($tagsPo + 'radar')
      $t2 = New-Task "Publicar item en Radar - $($po.name)"            $area $iter $ass $radarId ($tagsPo + 'radar')
      $out["radar-$($po.name)"] = @{ req=$radarId; tasks=@($t1,$t2) }
    }
  }

  # 3) Knowledge req (Sprint-02) — only for areas
  if ($po.hasArea) {
    $kTitle = "Primer articulo en Knowledge - $($po.name)"
    $kId = Get-ReqId $kTitle
    if ($kId) {
      $iter = 'Algoritmia IA\2026\Q2\Sprint-02'
      $t1 = New-Task "Identificar tema del articulo Knowledge - $($po.name)" $area $iter $ass $kId ($tagsPo + 'knowledge')
      $t2 = New-Task "Redactar articulo Knowledge - $($po.name)"             $area $iter $ass $kId ($tagsPo + 'knowledge')
      $t3 = New-Task "Publicar articulo en Knowledge - $($po.name)"          $area $iter $ass $kId ($tagsPo + 'knowledge')
      $out["knowledge-$($po.name)"] = @{ req=$kId; tasks=@($t1,$t2,$t3) }
    }
  }
}

Write-Host "`n=== Saving tasks.json ==="
$out | ConvertTo-Json -Depth 5 | Out-File -Encoding UTF8 .\scripts\tasks.json
Write-Host ("Total tasks tracked: {0}" -f $taskMap.Count)
