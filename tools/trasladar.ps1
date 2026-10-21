param(
    [Parameter(Mandatory, Position=0)][ValidateSet('iniciar','respaldar','restaurar')][string]$Accion,
    [Parameter(Position=1)][string]$Archivo,
    [string]$ComposeFile = 'docker-compose.yml',
    [string]$Perfil = '',
    [switch]$ConfirmarRestauracion
)
$ErrorActionPreference = 'Stop'
$raizProyecto = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $raizProyecto
Add-Type -AssemblyName System.IO.Compression.FileSystem

function dc {
    if ($Perfil) { & docker compose -f $ComposeFile --profile $Perfil @args }
    else { & docker compose -f $ComposeFile @args }
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose no completo la operacion.' }
}
function dockerOk {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw 'Docker no completo la operacion.' }
}
function ConfiguracionLocal {
    $script:apiId = (dc ps -q api | Out-String).Trim()
    $script:mongoId = (dc ps -q mongo | Out-String).Trim()
    if (!$apiId -or !$mongoId) { throw 'Inicia primero el sistema.' }
    $config = (dc exec -T api python -c "import json; from urllib.parse import urlparse; from app.core.config import settings; print(json.dumps({'db':settings.mongo_db,'local':urlparse(settings.mongo_uri).hostname=='mongo','uploads':settings.upload_dir}))" | Out-String) | ConvertFrom-Json
    if (!$config.local -or $config.db -notmatch '^[A-Za-z0-9_-]+$' -or !$config.uploads.StartsWith('/data/') -or $config.uploads.Split('/') -contains '..') {
        throw 'El traslado requiere MongoDB local y adjuntos dentro de /data/.'
    }
    return $config
}
function EscribirJson($ruta, $valor) {
    [IO.File]::WriteAllText($ruta, ($valor | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
}

if ($Accion -eq 'iniciar') {
    if (!(Test-Path -LiteralPath '.env')) {
        $bytes = New-Object byte[] 48
        $azar = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $azar.GetBytes($bytes) } finally { $azar.Dispose() }
        $clave = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
        $texto = [IO.File]::ReadAllText((Join-Path $raizProyecto '.env.example')) -replace '(?m)^SECRET_KEY=.*$', "SECRET_KEY=$clave"
        [IO.File]::WriteAllText((Join-Path $raizProyecto '.env'), $texto, [Text.UTF8Encoding]::new($false))
        Write-Host '.env creado con una clave aleatoria; configura el chatbot por separado.'
    }
    dc up -d --build --wait --wait-timeout 180
    Write-Host 'Sistema iniciado. Abre http://localhost o http://localhost:8080.'
    exit
}
if (!$Archivo) { throw 'Indica el archivo de respaldo.' }
$config = ConfiguracionLocal
$rutaArchivo = [IO.Path]::GetFullPath($Archivo)
if ($Accion -eq 'respaldar' -and !$rutaArchivo.EndsWith('.helpdesk.zip', [StringComparison]::OrdinalIgnoreCase)) { throw 'Usa la extension .helpdesk.zip para excluir el respaldo de Git.' }
if ($Accion -eq 'respaldar' -and (Test-Path -LiteralPath $rutaArchivo)) { throw 'El respaldo ya existe; elige otro nombre.' }
if ($Accion -eq 'restaurar') {
    $ocupado = (dc exec -T api python -c "import asyncio; from app.core.db import get_db,close_connections`nasync def main():`n db=get_db(); total=0`n for c in await db.list_collection_names():`n  if c not in {'_migraciones','catalogos','esquemas_tipos','configuracion','contadores'}: total+=await db[c].count_documents({})`n print(total); await close_connections()`nasyncio.run(main())" | Out-String).Trim()
    if ([int]$ocupado -gt 0) { throw 'El destino ya contiene datos. Solo se restaura sobre una instalacion nueva y vacia.' }
}
$carpetaTemporal = Join-Path ([IO.Path]::GetTempPath()) ('helpdesk-' + [guid]::NewGuid().ToString('N'))
$archivoMongo = '/tmp/traslado-' + [guid]::NewGuid().ToString('N') + '.gz'
$pausados = @()
New-Item -ItemType Directory -Path $carpetaTemporal | Out-Null
try {
    if ($Accion -eq 'restaurar') {
        $zip = [IO.Compression.ZipFile]::OpenRead($rutaArchivo)
        try {
            foreach ($entrada in $zip.Entries) {
                $destino = [IO.Path]::GetFullPath((Join-Path $carpetaTemporal $entrada.FullName))
                if (!$destino.StartsWith($carpetaTemporal + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta no permitida en el respaldo.' }
            }
        } finally { $zip.Dispose() }
        [IO.Compression.ZipFile]::ExtractToDirectory($rutaArchivo, $carpetaTemporal)
        $manifiesto = Get-Content -LiteralPath (Join-Path $carpetaTemporal 'manifiesto.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($manifiesto.formato -ne 1 -or $manifiesto.base -notmatch '^[A-Za-z0-9_-]+$' -or !$manifiesto.archivos.'mongo.gz') { throw 'Respaldo incompatible.' }
        $esperados = @('manifiesto.json') + @($manifiesto.archivos.PSObject.Properties.Name)
        Get-ChildItem -LiteralPath $carpetaTemporal -File -Recurse | ForEach-Object {
            $relativo = $_.FullName.Substring($carpetaTemporal.Length + 1).Replace('\','/')
            if ($esperados -cnotcontains $relativo) { throw 'Archivo no declarado en el manifiesto.' }
        }
        foreach ($propiedad in $manifiesto.archivos.PSObject.Properties) {
            if ($propiedad.Name -cne 'mongo.gz' -and !$propiedad.Name.StartsWith('uploads/')) { throw 'Archivo no permitido en el manifiesto.' }
            $destino = [IO.Path]::GetFullPath((Join-Path $carpetaTemporal $propiedad.Name))
            if (!$destino.StartsWith($carpetaTemporal + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta no permitida en el manifiesto.' }
            if ((Get-FileHash -LiteralPath $destino -Algorithm SHA256).Hash.ToLowerInvariant() -ne $propiedad.Value.ToLowerInvariant()) { throw 'Integridad incorrecta: no se restauro ningun dato.' }
        }
        if (!$ConfirmarRestauracion -and (Read-Host 'Escribe RESTAURAR para continuar') -cne 'RESTAURAR') { Write-Host 'Cancelado.'; return }
    }
    $activos = @(dc ps --status running --services)
    $pausados = @(@('api','worker') | Where-Object { $activos -contains $_ })
    if ($pausados.Count) { dc stop @pausados }
    if ($Accion -eq 'respaldar') {
        dockerOk exec $mongoId mongodump --quiet --host=127.0.0.1:27017 "--db=$($config.db)" --gzip "--archive=$archivoMongo"
        dockerOk cp "${mongoId}:$archivoMongo" (Join-Path $carpetaTemporal 'mongo.gz')
        $carpetaAdjuntos = Join-Path $carpetaTemporal 'uploads'
        New-Item -ItemType Directory -Path $carpetaAdjuntos | Out-Null
        dockerOk cp "${apiId}:$($config.uploads)/." $carpetaAdjuntos
        $archivos = @{}
        Get-ChildItem -LiteralPath $carpetaTemporal -File -Recurse | ForEach-Object {
            $nombre = $_.FullName.Substring($carpetaTemporal.Length + 1).Replace('\','/')
            $archivos[$nombre] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        EscribirJson (Join-Path $carpetaTemporal 'manifiesto.json') @{formato=1; base=$config.db; creado_utc=[DateTime]::UtcNow.ToString('o'); archivos=$archivos}
        $directorioDestino = Split-Path $rutaArchivo -Parent
        New-Item -ItemType Directory -Path $directorioDestino -Force | Out-Null
        [IO.Compression.ZipFile]::CreateFromDirectory($carpetaTemporal, $rutaArchivo)
        Write-Host "Respaldo creado: $rutaArchivo. Contiene datos privados; no lo subas a GitHub."
    } else {
        dockerOk cp (Join-Path $carpetaTemporal 'mongo.gz') "${mongoId}:$archivoMongo"
        dockerOk exec $mongoId mongorestore --quiet --host=127.0.0.1:27017 --gzip "--archive=$archivoMongo" "--nsFrom=$($manifiesto.base).*" "--nsTo=$($config.db).*" --drop
        if (Test-Path -LiteralPath (Join-Path $carpetaTemporal 'uploads')) { dockerOk cp ((Join-Path $carpetaTemporal 'uploads') + '/.') "${apiId}:$($config.uploads)" }
        $imagen = (dockerOk inspect --format '{{.Image}}' $apiId | Out-String).Trim()
        dockerOk run --rm --user root --volumes-from $apiId --entrypoint chown $imagen -R 10001:10001 $config.uploads
        Write-Host 'Base y adjuntos restaurados. Inicia sesion de nuevo.'
    }
} finally {
    dockerOk exec $mongoId rm -f $archivoMongo
    if ($pausados.Count) { dc start @pausados }
    # Solo se elimina el directorio temporal absoluto creado por este script.
    $temporalResuelto = [IO.Path]::GetFullPath($carpetaTemporal)
    $raizTemporal = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($temporalResuelto.StartsWith($raizTemporal, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path $temporalResuelto -Leaf) -like 'helpdesk-*') {
        Remove-Item -LiteralPath $temporalResuelto -Recurse -Force
    }
}
