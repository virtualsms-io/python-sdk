#!/bin/sh
#
# check-positioning.sh - VirtualSMS positioning and number drift guard.
#
# Fails (exit 1) if any tracked, human-authored file in this repo contains
# copy that contradicts the canonical brand values (stale service/country
# counts, banned framing, infrastructure or supplier leaks, em/en dashes).
#
# Canonical source of truth: Vault/Design/canonical.json
#
# Usage:  sh scripts/check-positioning.sh
#
# Design notes:
#   - Scans TRACKED files only (git grep), so ignored/vendored trees are
#     already out of scope. The exclude pathspecs below are belt-and-braces.
#   - This script necessarily contains every banned string, so it excludes
#     itself (see ":(exclude)$SELF"). Without that it always fails on itself.
#   - Globbing is disabled (set -f) so pathspec wildcards reach git intact
#     instead of being expanded by the shell first.

set -uf

SELF="scripts/check-positioning.sh"
CANON_MSG="Canonical source: Vault/Design/canonical.json"

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "check-positioning: not inside a git repository" >&2
    exit 2
}
cd "$root" || exit 2

# Newline-separated pathspecs, expanded UNQUOTED on purpose so each becomes a
# separate argument. No entry may contain a space.
SCOPE=":(exclude)$SELF
:(glob,exclude)**/node_modules/**
:(glob,exclude)**/vendor/**
:(glob,exclude)**/dist/**
:(glob,exclude)**/build/**
:(glob,exclude)**/bin/**
:(glob,exclude)**/obj/**
:(glob,exclude)**/package-lock.json
:(glob,exclude)**/composer.lock
:(glob,exclude)**/Gemfile.lock
:(glob,exclude)**/poetry.lock"

# Package manifests whose description fields must stay dash-free.
MANIFESTS=package.json
MANIFESTS="$MANIFESTS
setup.py
pyproject.toml
composer.json
*.gemspec
*.csproj
*.nuspec"

findings=$(mktemp) || exit 2
trap 'rm -f "$findings"' EXIT INT TERM

# emit <git-grep-output> <label> <reason>
emit() {
    printf '%s\n' "$1" | while IFS= read -r _hit; do
        printf '%s\n      banned term: "%s"  (%s)\n' "$_hit" "$2" "$3" >> "$findings"
    done
}

# banned <reason> <literal term>   - plain substring match
banned() {
    _out=$(git grep -I -n -i -F -e "$2" -- . $SCOPE 2>/dev/null)
    [ -n "$_out" ] && emit "$_out" "$2" "$1"
    return 0
}

# banned_num <reason> <label> <ERE>  - numeric claim match
# Numeric bans carry a "not preceded by another digit" guard: without it a ban
# on "500+ services" also matches the CANONICAL "2500+ services", and a ban on
# "30+ countries" matches "130+ countries". The guard consumes the preceding
# character, which is harmless because git grep reports whole lines anyway.
banned_num() {
    _out=$(git grep -I -n -i -E -e "(^|[^0-9])$3" -- . $SCOPE 2>/dev/null)
    [ -n "$_out" ] && emit "$_out" "$2" "$1"
    return 0
}

# banned_re <reason> <label> <ERE>  - case-insensitive regex match
# For bans that need alternation. Keep patterns PRECISE: a guard that flags
# legitimate copy gets deleted, which is worse than no guard at all.
banned_re() {
    _out=$(git grep -I -n -i -E -e "$3" -- . $SCOPE 2>/dev/null)
    [ -n "$_out" ] && emit "$_out" "$2" "$1"
    return 0
}

# --- wrong numbers ------------------------------------------------------
banned_num "canonical services count is 2500+" "700+ services" '700\+ services'
banned_num "canonical services count is 2500+" "500+ services" '500\+ services'
banned_num "canonical number countries is 145+" "30+ countries" '30\+ countries'
banned_num "canonical number countries is 145+" "200+ countries" '200\+ countries'
banned_num "canonical published MCP tool count is 18" "12 tools" '12 tools'
banned_num "unsupported claim; canonical success framing is 95%+" "90%+ of VoIP" '90%\+ of VoIP'
banned "canonical min price per code is \$0.05" '$0.02'
banned "canonical success framing is 95%+" "near-100"

# --- banned framing -----------------------------------------------------
# NOTE: "physical SIM" is deliberately NOT banned. Real physical SIM cards are
# the product and an approved differentiator (operator ruling 2026-07-16):
# "real physical sims is ok! its actually a differentiator, and nothing is
# leaking about location here". The SIM is the PRODUCT and is allowed; the
# modem and where it sits are OUR INFRASTRUCTURE and stay banned below.
banned "unverifiable ranking claim" "Ranked #1"
banned "unverifiable ranking claim" "#1 on"
banned "unverifiable ranking claim" "#1 in"
banned "banned framing" "not a reseller"
banned "banned framing" "direct-sourced"
banned "banned framing" "agentic"

# --- infrastructure leak ------------------------------------------------
banned "infra leak; never describe our hardware" "modem"
banned "infra leak; never describe our hardware" "SIM box"
banned "infra leak; never describe our fleet" "our fleet"
banned "infra leak; never reveal where our hardware sits" "our EU"
banned "infra leak; never describe our hardware" "our hardware"
banned "infra leak; never reveal port or SIM counts" "ports across"

# --- infrastructure LOCATION leak (our-fleet location) ------------------
# The OUR-vs-PRODUCT test: saying where OUR SIMs/fleet/hardware sit is banned;
# describing the PRODUCT or its coverage is fine.
#
# These patterns are deliberately narrow. They must NOT fire on legitimate
# copy, all of which is verified to pass:
#   "2500+ services in 145+ countries"      (coverage)
#   "real carrier-issued SIM cards across 145+ countries"
#   "Vodafone", "O2", "T-Mobile", "Telekom" (carrier names are allowed)
#   "a German number runs on Telekom/Vodafone/O2"
# Anchor on a location word next to OUR inventory, never on a bare region
# word and never on a country/carrier name.
LOC='european|eu|us|usa|europe|united states'
banned_re "infra leak; never say where our SIMs are" \
    "SIM cards in <region>" "sim cards? in (the )?($LOC)([^a-zA-Z]|\$)"
banned_re "infra leak; never say where our SIMs are" \
    "SIMs in <region>" "sims? in (the )?($LOC)([^a-zA-Z]|\$)"
banned_re "infra leak; never say where our SIMs are" \
    "<region> mobile networks" "($LOC) mobile networks"
banned_re "infra leak; never say where our fleet is" \
    "our <inventory> are in <region>" \
    "our (sims?|numbers|fleet|infrastructure|hardware) (are|is|sit|sits|live|lives) in"

# --- supplier leak ------------------------------------------------------
# SCOPE NOTE, read before copying these lines anywhere else:
# These are FLAT name bans, which is safe ONLY because an SDK repo carries no
# competitor-comparison content. The names below are also public COMPETITORS,
# and naming them in competitor context ("Alternative to TextVerified", vs
# tables, /textverified-alternative) is ALLOWED and SEO-valuable (operator
# ruling 2026-07-02). Do NOT copy this flat ban into the website, frontend or
# marketing-site: it would flag /textverified-alternative, the best-performing
# page. There, ban the SUPPLY phrasing ("our TextVerified integration",
# "sourced from X"), never the bare name.
# Canonical rule: Vault/CLAUDE.md "No provider / supplier-name leak".
banned "supplier leak; we sell via our own platform" "HeroSMS"
banned "supplier leak; we sell via our own platform" "hero-sms"
banned "supplier leak; we sell via our own platform" "TextVerified"
banned "supplier leak; we sell via our own platform" "text-verified"

# --- em-dash / en-dash --------------------------------------------------
# Built with printf so the script stays pure ASCII and encoding-safe.
EM=$(printf '\342\200\224')   # U+2014 em dash
EN=$(printf '\342\200\223')   # U+2013 en dash

dash_hits() {
    _label=$1
    _spec=$2
    _out=$(git grep -I -n -F -e "$EM" -e "$EN" -- $_spec $SCOPE 2>/dev/null)
    [ -n "$_out" ] || return 0
    printf '%s\n' "$_out" | while IFS= read -r _hit; do
        printf '%s\n      banned term: em-dash or en-dash  (%s; use a colon, comma or full stop)\n' \
            "$_hit" "$_label" >> "$findings"
    done
}

dash_hits "not allowed in README" "*README.md"
dash_hits "not allowed in a package manifest description" "$MANIFESTS"

# --- verdict ------------------------------------------------------------
if [ -s "$findings" ]; then
    echo "check-positioning: FAILED - banned copy found"
    echo
    sed 's/^/  /' "$findings"
    echo
    echo "  Each hit is file:line: followed by the offending text."
    echo "  Fix the copy to match canonical values, do not weaken this check."
    echo "  $CANON_MSG"
    exit 1
fi

echo "check-positioning: OK - no banned copy in tracked files. ($CANON_MSG)"
exit 0
