# shellcheck shell=bash
# Reading and writing single settings in the instance's .env, for the
# host scripts. Sourced, not run; both functions act on .env in the
# current directory.

# The last assignment of KEY in .env, without surrounding quotes.
env_value() {
    sed -n "s/^$1=//p" .env | tail -n 1 | sed "s/^[\"']//; s/[\"']\$//"
}

# Replace KEY's line in .env, or append one. A value holding anything
# but letters, digits and . _ - / : @ + is written in single quotes,
# which docker compose reads literally, $ included; a value holding a
# single quote or a newline is refused. The file is rewritten with mode
# 0600, since it holds the instance's secrets.
set_env_value() {
    local key=$1 value=$2 plain='^[A-Za-z0-9._/:@+-]*$'
    case $value in
        *\'* | *$'\n'*)
            echo "set_env_value: $key: a value cannot hold a single quote or a newline" >&2
            return 1
            ;;
    esac
    [[ $value =~ $plain ]] || value="'$value'"
    (
        umask 077
        # Through the environment: awk -v would read backslash escapes.
        ENV_FILE_VALUE=$value awk -v key="$key" '
            index($0, key "=") == 1 {
                if (!done) print key "=" ENVIRON["ENV_FILE_VALUE"]
                done = 1
                next
            }
            { print }
            END { if (!done) print key "=" ENVIRON["ENV_FILE_VALUE"] }
        ' .env > .env.update
    )
    mv .env.update .env
}
