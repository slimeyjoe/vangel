#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Keeps private information out of the repository.
#
#   scripts/check-leaks.sh tree            the tracked and staged files
#   scripts/check-leaks.sh msg FILE        a commit message (commit-msg hook)
#   scripts/check-leaks.sh commits RANGE   authors, committers and messages of commits
#   scripts/check-leaks.sh install         install the git hooks of this clone
#
# Two pattern sets are applied. The generic one below catches machine-specific paths and
# hosts. A maintainer's own list (names, addresses, hosts; one extended regular expression per
# line, # comments) is read from .git/info/leak-patterns when it exists: it is never tracked,
# because the list itself is what must not be published.
set -eu

root=$(git rev-parse --show-toplevel)
cd "$root"
private="$(git rev-parse --git-common-dir)/info/leak-patterns"
self=scripts/check-leaks.sh

generic='(/home/[a-z_]|/Users/[A-Za-z_]|~/repos|~/Downloads|\.venvs/|/storage/|/mnt/|[a-z0-9-]+\.local[:/ ]|[a-z0-9-]+\.lan[:/ ])'

patterns() {
    printf '%s\n' "$generic"
    if [ -f "$private" ]; then
        grep -v '^[[:space:]]*\(#\|$\)' "$private" || true
    fi
}

# the identity every commit of this repository must carry
want_name=$(git config --local user.name || true)
want_email=$(git config --local user.email || true)

scan_stdin() {  # $1 = label; fails when a pattern matches stdin
    pats=$(mktemp)
    patterns >"$pats"
    if grep -nEf "$pats" >"$pats.hits"; then
        echo "check-leaks: $1:" >&2
        sed 's/^/    /' "$pats.hits" >&2
        rm -f "$pats" "$pats.hits"
        return 1
    fi
    rm -f "$pats" "$pats.hits"
}

check_tree() {
    pats=$(mktemp)
    patterns >"$pats"
    rc=0
    # tracked and staged text files, except this script and vendored code
    git ls-files -z --cached | grep -zv -e "^$self\$" -e '^third_party/' -e '^LICENSE$' |
        xargs -0 -r grep -InHEf "$pats" -- >"$pats.hits" 2>/dev/null || true
    if [ -s "$pats.hits" ]; then
        echo "check-leaks: private or machine-specific text in tracked files:" >&2
        sed 's/^/    /' "$pats.hits" >&2
        rc=1
    fi
    rm -f "$pats" "$pats.hits"
    return $rc
}

check_identity() {  # the identity the next commit would get
    if [ -z "$want_name" ] || [ -z "$want_email" ]; then
        echo "check-leaks: set user.name and user.email in this clone (git config --local)" >&2
        return 1
    fi
    for who in AUTHOR COMMITTER; do
        ident=$(git var GIT_${who}_IDENT)
        case "$ident" in
        "$want_name <$want_email> "*) ;;
        *)
            echo "check-leaks: $who would be '${ident% * *}', expected '$want_name <$want_email>'" >&2
            return 1
            ;;
        esac
    done
}

check_commits() {  # $1 = revision range or list
    rc=0
    for c in $(git rev-list "$@"); do
        ids=$(git show -s --format='%an <%ae>%n%cn <%ce>' "$c" | sort -u)
        if [ "$ids" != "$want_name <$want_email>" ]; then
            echo "check-leaks: commit $c has identity:" >&2
            echo "$ids" | sed 's/^/    /' >&2
            rc=1
        fi
        git show -s --format=%B "$c" | scan_stdin "message of commit $c" || rc=1
    done
    return $rc
}

install_hooks() {
    hooks="$(git rev-parse --git-common-dir)/hooks"
    mkdir -p "$hooks"
    cat >"$hooks/pre-commit" <<'EOF'
#!/bin/sh
exec scripts/check-leaks.sh pre-commit
EOF
    cat >"$hooks/commit-msg" <<'EOF'
#!/bin/sh
exec scripts/check-leaks.sh msg "$1"
EOF
    cat >"$hooks/pre-push" <<'EOF'
#!/bin/sh
# stdin: <local ref> <local sha> <remote ref> <remote sha>
zero=0000000000000000000000000000000000000000
rc=0
while read -r _ lsha _ rsha; do
    [ "$lsha" = "$zero" ] && continue
    if [ "$rsha" = "$zero" ]; then range="$lsha"; else range="$rsha..$lsha"; fi
    scripts/check-leaks.sh commits $range || rc=1
done
scripts/check-leaks.sh tree || rc=1
exit $rc
EOF
    chmod +x "$hooks/pre-commit" "$hooks/commit-msg" "$hooks/pre-push"
    echo "check-leaks: hooks installed in $hooks"
}

case "${1:-tree}" in
tree) check_tree ;;
pre-commit) check_identity && check_tree ;;
msg) scan_stdin "commit message" <"$2" ;;
commits) shift; check_commits "$@" ;;
install) install_hooks ;;
*) echo "usage: $0 [tree | msg FILE | commits RANGE | install]" >&2; exit 2 ;;
esac
