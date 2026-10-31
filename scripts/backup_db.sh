#!/bin/sh
# Резервная копия БД стенда перед изменением схемы: pg_dump в формате custom (-Fc), проверка, что копия читается
# (pg_restore --list), хранятся 10 последних копий.
#
# Запуск — из каталога со стеком docker compose, где есть сервис db (PostgreSQL с переменными POSTGRES_USER и
# POSTGRES_DB):
#     scripts/backup_db.sh
#
# Копии остаются на сервере в ~/backups и никуда не выгружаются: в БД персональные данные пользователей
# и зашифрованные токены личного кабинета.
set -eu

mkdir -p "$HOME/backups"
file="$HOME/backups/mospolytech-$(date +%Y%m%d-%H%M%S).dump"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$file"

echo "Backup contents (tables):"
docker compose exec -T db pg_restore --list < "$file" | grep -E ' TABLE (DATA )?public ' | head -30
ls -l "$file"

# старые копии сверх десяти последних удаляем
ls -1t "$HOME"/backups/mospolytech-*.dump | tail -n +11 | xargs -r rm --
