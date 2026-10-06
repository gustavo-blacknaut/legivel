#!/bin/sh
set -eu

. "$(dirname "$0")/backup-common.sh"
require_passphrase

output_dir=${1:-"$root/backups"}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$output_dir/legivel-$stamp.tar.gz.gpg"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
umask 077
mkdir -p "$output_dir"

echo "Copiando o banco..."
compose exec -T postgres pg_dump -U "$database_user" -d "$database_name" -Fc > "$work/banco.dump"
echo "Copiando as imagens de $storage_path..."
docker run --rm -v "$storage_path:/data:ro" "$helper_image" tar -C /data -cf - . > "$work/storage.tar"
printf 'legivel-backup 1\ncriado_em=%s\nbanco=%s\n' "$stamp" "$database_name" > "$work/MANIFEST"
(cd "$work" && sha256sum banco.dump storage.tar > SHA256SUMS)

echo "Cifrando..."
tar -C "$work" -czf "$work/backup.tar.gz" MANIFEST SHA256SUMS banco.dump storage.tar
gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$passphrase_file" \
    --symmetric --cipher-algo AES256 --output "$target.parcial" "$work/backup.tar.gz"
mv "$target.parcial" "$target"
echo "Backup salvo em $target"
