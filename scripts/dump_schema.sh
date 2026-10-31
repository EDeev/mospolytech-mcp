#!/bin/sh
# Выгружает актуальную схему БД стандартным pg_dump --schema-only в стабильном виде (для db/schema/schema.sql).
#
# Запуск — из каталога со стеком docker compose, где есть сервис db (PostgreSQL с переменными POSTGRES_USER и
# POSTGRES_DB) и к БД уже применены миграции:
#     scripts/dump_schema.sh > db/schema/schema.sql
#
# Из вывода убираются строки-комментарии (в них версии pg_dump и сервера), строки \restrict и \unrestrict
# (pg_dump 17.6+ пишет в них случайный ключ при каждом запуске), повторные пустые строки и пустые строки в начале
# и в конце — так две выгрузки одинаковых схем совпадают побайтно, а diff файла показывает только изменения схемы.
set -eu

dump=$(docker compose exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only --no-owner --no-privileges')

printf '%s\n' "$dump" \
    | sed -e '/^\\restrict /d' -e '/^\\unrestrict /d' -e '/^--/d' \
    | awk 'NF { if (blank && printed) print ""; print; printed = 1; blank = 0; next } { blank = 1 }'
