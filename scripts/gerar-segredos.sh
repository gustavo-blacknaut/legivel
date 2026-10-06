#!/bin/sh
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
secrets_dir="$root/secrets"
env_file="$root/.env"

value_from_env() {
    [ -f "$env_file" ] || return 0
    sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d '\r' | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

random_password() {
    openssl rand -base64 33 | tr -d '/+=\n'
}

random_key() {
    openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'
}

write_secret() {
    name=$1
    variable=$2
    generator=$3
    target="$secrets_dir/$name"
    if [ -s "$target" ]; then
        echo "$name: mantido"
        return
    fi
    value=""
    if [ -n "$variable" ]; then
        value=$(value_from_env "$variable")
    fi
    if [ -n "$value" ]; then
        origin="copiado de $variable no .env"
    else
        value=$($generator)
        origin="gerado"
    fi
    printf '%s' "$value" > "$target"
    chmod 644 "$target"
    echo "$name: $origin"
}

umask 077
mkdir -p "$secrets_dir"
chmod 700 "$secrets_dir"
write_secret postgres_password POSTGRES_PASSWORD random_password
write_secret database_app_password "" random_password
write_secret secret_key LEGIVEL_SECRET_KEY random_key
write_secret encryption_key LEGIVEL_ENCRYPTION_KEY random_key
write_secret backup_passphrase "" random_password
echo "Segredos em $secrets_dir. Guarde uma cópia de encryption_key e de backup_passphrase fora do servidor: sem elas as imagens e os backups não podem ser lidos."
