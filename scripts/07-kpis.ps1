$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$proj = 'Algoritmia IA'

# Feature ids (vigilancia / knowledge) per area, from features.json
$features = Get-Content .\scripts\features.json -Raw -Encoding UTF8 | ConvertFrom-Json
$fMap = @{}
foreach ($p in $features.PSObject.Properties) { $fMap[$p.Name] = $p.Value }

# Areas (skip Coordinacion: no KPI mensual de aportacion)
$areas = @(
  @{ name='Customer Engagement';areaPath='Algoritmia IA\Customer Engagement';ass='martero@algoritmia8.com';  fkey='Customer_Engagement'      },
  @{ name='Business Central';   areaPath='Algoritmia IA\Business Central';   ass='lflorido@algoritmia8.com'; fkey='Business_Central'         },
  @{ name='Finance';            areaPath='Algoritmia IA\Finance';            ass='ofolques@algoritmia8.com'; fkey='Finance'                  },
  @{ name='SCM';                areaPath='Algoritmia IA\SCM';                ass=$null;                       fkey='SCM'                      },
  @{ name='Prog. Finance-PP';   areaPath='Algoritmia IA\Prog. Finance-PP';   ass='asalas@algoritmia8.com';   fkey='Programacion_Finance_PP'  },
  @{ name='Prog. Web-Data';     areaPath='Algoritmia IA\Prog. Web-Data';     ass='promero@algoritmia8.com';  fkey='Programacion_Web_Data'    },
  @{ name='Azure';              areaPath='Algoritmia IA\Azure';              ass='cgelonch@algoritmia8.com'; fkey='Azure'                    }
)

# Months Jun-Dic 2026 -> iteration
# Sprint-01 18-may, S2 01-jun, S3 15-jun, S4 29-jun, S5 13-jul, S6 27-jul, S7 10-ago, S8 24-ago, S9 07-sep, S10 21-sep,
# S11 05-oct, S12 19-oct, S13 02-nov, S14 16-nov, S15 30-nov
# Pick first sprint of each month
$monthIter = @{
  'Jun 2026' = 'Algoritmia IA\2026\Q2\Sprint-02'
  'Jul 2026' = 'Algoritmia IA\2026\Q3\Sprint-05'
  'Ago 2026' = 'Algoritmia IA\2026\Q3\Sprint-07'
  'Sep 2026' = 'Algoritmia IA\2026\Q3\Sprint-09'
  'Oct 2026' = 'Algoritmia IA\2026\Q4\Sprint-11'
  'Nov 2026' = 'Algoritmia IA\2026\Q4\Sprint-13'
  'Dic 2026' = 'Algoritmia IA\2026\Q4\Sprint-15'
}
$monthOrder = @('Jun 2026','Jul 2026','Ago 2026','Sep 2026','Oct 2026','Nov 2026','Dic 2026')

# Pre-load existing Requirements to dedup
Write-Host 'Loading existing Requirements...'
$wiql = "SELECT [System.Id],[System.Title] FROM WorkItems WHERE [System.TeamProject]='Algoritmia IA' AND [System.WorkItemType]='Requirement'"
$existing = az boards query --wiql $wiql -o json | ConvertFrom-Json
$reqMap = @{}
foreach ($e in $existing) { $reqMap[$e.fields.'System.Title'] = $e.id }
Write-Host ("Found {0} existing requirements." -f $reqMap.Count)

function New-Req([string]$title, [string]$area, [string]$iter, [string]$assigned, [int]$parentId, [string[]]$tags) {
  if ($reqMap.ContainsKey($title)) {
    Write-Host ("  SKIP '{0}' -> #{1}" -f $title, $reqMap[$title])
    return $reqMap[$title]
  }
  $args = @('boards','work-item','create','--project',$proj,'--type','Requirement','--title',$title,'--area',$area,'--iteration',$iter)
  if ($assigned) { $args += @('--assigned-to',$assigned) }
  if ($tags -and $tags.Count -gt 0) { $args += @('--fields', ('System.Tags=' + ($tags -join '; '))) }
  $args += @('-o','json')
  $json = & az @args 2>$null
  if (-not $json) { Write-Host ("  FAILED '{0}'" -f $title) -ForegroundColor Red; return $null }
  $w = $json | ConvertFrom-Json
  $id = $w.id
  if ($parentId) { az boards work-item relation add --id $id --relation-type Parent --target-id $parentId -o none 2>$null | Out-Null }
  Write-Host ("  -> Req #{0} : {1}" -f $id, $title)
  $reqMap[$title] = $id
  return $id
}

$out = @{}

foreach ($a in $areas) {
  Write-Host ("`n=== {0} ===" -f $a.name)
  $tagsBase = @('kpi-mensual','recurrente')
  if (-not $a.ass) { $tagsBase += 'po-pendiente' }

  $featRadarKey = ('Radar_'     + $a.fkey)
  $featKnowKey  = ('Knowledge_' + $a.fkey)
  $parentRadar = $fMap[$featRadarKey]
  $parentKnow  = $fMap[$featKnowKey]

  foreach ($m in $monthOrder) {
    $iter = $monthIter[$m]
    $tR = "[$m] Aportar >=2 items al Radar - $($a.name)"
    $tK = "[$m] Publicar >=1 articulo en Knowledge - $($a.name)"
    $idR = New-Req $tR $a.areaPath $iter $a.ass $parentRadar ($tagsBase + 'radar')
    $idK = New-Req $tK $a.areaPath $iter $a.ass $parentKnow  ($tagsBase + 'knowledge')
    $out["$($a.name)|$m|radar"]     = $idR
    $out["$($a.name)|$m|knowledge"] = $idK
  }
}

Write-Host "`n=== Saving kpis.json ==="
$out | ConvertTo-Json -Depth 5 | Out-File -Encoding UTF8 .\scripts\kpis.json
Write-Host ("Total tracked: {0}" -f $reqMap.Count)
