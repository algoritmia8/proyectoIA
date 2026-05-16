$ErrorActionPreference = "Continue"
$proj = "Algoritmia IA"

$pos = @(
  "ifont@algoritmia8.com",
  "rplana@algoritmia8.com",
  "martero@algoritmia8.com",
  "lflorido@algoritmia8.com",
  "ofolques@algoritmia8.com",
  "dgaya@algoritmia8.com",
  "asalas@algoritmia8.com",
  "promero@algoritmia8.com",
  "cgelonch@algoritmia8.com"
)

foreach ($u in $pos) {
    Write-Host "=== $u ==="
    az devops user show --user $u --query "{name:user.displayName,email:user.mailAddress,principalName:user.principalName}" -o json
}
