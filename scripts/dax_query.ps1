# Exécute une requête DAX sur le modèle ouvert dans Power BI Desktop (moteur local).
# Usage (Windows PowerShell 5.1) : powershell -File scripts\dax_query.ps1 -Fichier requete.dax
#        Test RLS : -Role Acheteur -Utilisateur acheteur.cvc@buyvera.example
param([Parameter(Mandatory = $true)][string]$Fichier, [string]$Role = "", [string]$Utilisateur = "")

$ErrorActionPreference = 'Stop'
$asm = [System.Reflection.Assembly]::LoadFrom('C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll')
$typeCn = $asm.GetType('Microsoft.AnalysisServices.AdomdClient.AdomdConnection')

# Port du moteur encore en écoute (le plus récent d'abord ; une instance fermée laisse son fichier)
$ports = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces" -Recurse -Filter msmdsrv.port.txt |
    Sort-Object LastWriteTime -Descending |
    ForEach-Object { [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::Unicode).Trim() }
$port = $ports | Where-Object {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect('localhost', [int]$_); $true } catch { $false } finally { $c.Close() }
} | Select-Object -First 1
if (-not $port) { throw "Aucun moteur Power BI Desktop en ecoute : ouvrir le projet d'abord." }

$cs = "Data Source=localhost:$port"
if ($Role) { $cs += ";Roles=$Role" }
if ($Utilisateur) { $cs += ";EffectiveUserName=$Utilisateur" }
$cn = [Activator]::CreateInstance($typeCn, @($cs))
$cn.Open()
$cmd = $cn.CreateCommand()
$cmd.CommandText = [System.IO.File]::ReadAllText((Resolve-Path $Fichier), [System.Text.Encoding]::UTF8)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ($cmd.CommandText.TrimStart().StartsWith('{')) {
    # Commande TMSL (ex. refresh) : pas de jeu de résultats
    $cmd.CommandText = $cmd.CommandText.Replace('__DB__', $cn.Database)
    [void]$cmd.ExecuteNonQuery()
    Write-Output "TMSL exécuté sur $($cn.Database)"
    $cn.Close(); exit 0
}
$r = $cmd.ExecuteReader()
$cols = 0..($r.FieldCount - 1) | ForEach-Object { $r.GetName($_) }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output ($cols -join "`t")
while ($r.Read()) {
    $vals = 0..($r.FieldCount - 1) | ForEach-Object { $v = $r.GetValue($_); if ($v -is [double]) { $v.ToString('0.######', [Globalization.CultureInfo]::InvariantCulture) } else { "$v" } }
    Write-Output ($vals -join "`t")
}
$r.Close(); $cn.Close()
