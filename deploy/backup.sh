#!/usr/bin/env bash
# Respaldo programado de MongoDB con retencion configurable.
# Se ejecuta dentro del contenedor "backup" (perfil: backup).
#
#   docker compose --profile backup up -d backup
#
# Restaura documentada en README.md ("Restaurar un respaldo").
set -euo pipefail

MONGO_URI="${MONGO_URI:-mongodb://mongo:27017/?replicaSet=rs0}"
BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
RUN_HOUR="${BACKUP_CRON_HOUR:-2}"

mkdir -p "$BACKUP_DIR"

log() { echo "[backup $(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

run_backup() {
  local stamp ts_file
  stamp="$(date -u '+%Y%m%d-%H%M%S')"
  ts_file="${BACKUP_DIR}/ultimo-respaldo.txt"

  log "iniciando mongodump -> ${BACKUP_DIR}/respaldo-${stamp}"
  if mongodump --uri="$MONGO_URI" --archive="${BACKUP_DIR}/respaldo-${stamp}.gz" --gzip; then
    echo "$stamp" > "$ts_file"
    # Integridad: el archivo no debe estar vacio
    if [ ! -s "${BACKUP_DIR}/respaldo-${stamp}.gz" ]; then
      log "ERROR: el archivo de respaldo quedo vacio"
      return 1
    fi
    log "respaldo completado ($(du -h "${BACKUP_DIR}/respaldo-${stamp}.gz" | cut -f1))"
  else
    log "ERROR: mongodump fallo"
    return 1
  fi

  # Retencion
  log "purgando respaldos con mas de ${RETENTION_DAYS} dias"
  find "$BACKUP_DIR" -maxdepth 1 -name 'respaldo-*.gz' -type f -mtime "+${RETENTION_DAYS}" -print -delete || true
}

log "planificado: todos los dias a las ${RUN_HOUR}:00 UTC (retencion ${RETENTION_DAYS} dias)"

while true; do
  now_hour="$(date -u '+%-H')"
  # Marca el dia para no repetir el respaldo de hoy si el contenedor reinicia
  today="$(date -u '+%Y-%m-%d')"
  marker="/tmp/backup-hecho-${today}"
  if [ "$now_hour" -ge "$RUN_HOUR" ] && [ ! -f "$marker" ]; then
    run_backup && touch "$marker" || log "el respaldo de hoy fallo; se reintentara"
  fi
  sleep 300
done