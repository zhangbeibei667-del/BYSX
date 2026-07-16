param(
    [string]$MySqlPassword = "tcm_local_dev",
    [string]$Neo4jPassword = "tcm_local_dev"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $env:MYSQL_PASSWORD = $MySqlPassword
    $env:NEO4J_PASSWORD = $Neo4jPassword
    docker compose -f docker-compose.storage.yml up -d --wait
    if ($LASTEXITCODE -ne 0) {
        throw "Docker storage services failed to start. Start Docker Desktop and retry."
    }
    $env:STORE_BACKEND = "hybrid"
    $env:MYSQL_HOST = "127.0.0.1"
    $env:MYSQL_PORT = "3306"
    $env:MYSQL_USER = "root"
    $env:MYSQL_DATABASE = "tcm"
    $env:NEO4J_URI = "bolt://127.0.0.1:7687"
    $env:NEO4J_USER = "neo4j"

    python -m unittest server.test_functional
    if ($LASTEXITCODE -ne 0) {
        throw "Storage matrix verification failed with exit code $LASTEXITCODE"
    }
    Write-Host "Memory, MySQL, Neo4j and Hybrid storage verification passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
