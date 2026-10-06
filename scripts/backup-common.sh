root=$(cd "$(dirname "$0")/.." && pwd)
env_file="$root/.env"
passphrase_file="$root/secrets/backup_passphrase"
helper_image="alpine:3.24"
postgres_image="postgres:18.6-alpine3.24"

env_value() {
    value=""
    if [ -f "$env_file" ]; then
        value=$(sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d '\r' | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")
    fi
    printf '%s' "${value:-$2}"
}

database_user=$(env_value POSTGRES_USER legivel)
database_name=$(env_value POSTGRES_DB legivel)
storage_path=$(env_value LEGIVEL_STORAGE_PATH ./storage)
case "$storage_path" in
    /*) ;;
    *) storage_path="$root/${storage_path#./}" ;;
esac

require_passphrase() {
    if [ ! -s "$passphrase_file" ]; then
        echo "Falta secrets/backup_passphrase. Rode scripts/gerar-segredos.sh." >&2
        exit 1
    fi
}

compose() {
    (cd "$root" && docker compose "$@")
}
