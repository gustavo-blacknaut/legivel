#!/bin/sh
set -eu

. "$(dirname "$0")/backup-common.sh"
require_passphrase

usage() {
    echo "Uso: scripts/restaurar-backup.sh ARQUIVO.tar.gz.gpg [--verificar | --confirmar]" >&2
    echo "  --verificar  restaura num PostgreSQL temporário e confere, sem tocar na instalação" >&2
    echo "  --confirmar  substitui o banco e as imagens da instalação pelos do backup" >&2
    exit 2
}

[ $# -eq 2 ] || usage
archive=$1
mode=$2
[ -f "$archive" ] || { echo "Arquivo não encontrado: $archive" >&2; exit 1; }
case "$mode" in --verificar | --confirmar) ;; *) usage ;; esac

work=$(mktemp -d)
container=""
cleanup() {
    [ -z "$container" ] || docker rm -f "$container" > /dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT
umask 077

echo "Decifrando..."
if ! gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$passphrase_file" \
    --output "$work/backup.tar.gz" --decrypt "$archive" 2> "$work/gpg.log"; then
    echo "Não foi possível decifrar: senha de backup errada ou arquivo corrompido." >&2
    exit 1
fi
tar -C "$work" -xzf "$work/backup.tar.gz"
rm "$work/backup.tar.gz"
(cd "$work" && sha256sum -c --quiet SHA256SUMS)
grep -q '^legivel-backup 1$' "$work/MANIFEST" || { echo "Arquivo não é um backup do Legível." >&2; exit 1; }
echo "Integridade conferida ($(sed -n 's/^criado_em=//p' "$work/MANIFEST"))."

if [ "$mode" = "--verificar" ]; then
    container="legivel-restore-check-$$"
    docker run -d --name "$container" -e POSTGRES_PASSWORD=verificacao -e POSTGRES_DB=verificacao "$postgres_image" > /dev/null
    until docker exec "$container" pg_isready -U postgres -d verificacao > /dev/null 2>&1 \
        && docker exec "$container" psql -U postgres -d verificacao -c 'SELECT 1' > /dev/null 2>&1; do
        sleep 1
    done
    docker exec -i "$container" pg_restore -U postgres -d verificacao --no-owner --no-privileges --exit-on-error < "$work/banco.dump"
    counts=$(docker exec "$container" psql -U postgres -d verificacao -tA -F ' ' -c \
        "SELECT (SELECT count(*) FROM people), (SELECT count(*) FROM documents), (SELECT count(*) FROM document_images), (SELECT version_num FROM alembic_version)")
    set -- $counts
    files=$(tar -tf "$work/storage.tar" | grep -vc '/$' || true)
    echo "Restauração de teste concluída: $1 pessoa(s), $2 documento(s), $3 imagem(ns) no banco, $files arquivo(s) de imagem, migração $4."
    exit 0
fi

echo "Parando a API e a interface..."
compose stop web api
compose up -d --wait postgres
echo "Restaurando o banco..."
compose exec -T postgres pg_restore -U "$database_user" -d "$database_name" --clean --if-exists --no-owner --no-privileges \
    --exit-on-error < "$work/banco.dump"
echo "Restaurando as imagens em $storage_path..."
mkdir -p "$storage_path"
docker run --rm -i -v "$storage_path:/data" "$helper_image" \
    sh -c 'find /data -mindepth 1 -delete && tar -C /data -xf - && chown -R 10001 /data' < "$work/storage.tar"
compose up -d
echo "Restauração concluída."
