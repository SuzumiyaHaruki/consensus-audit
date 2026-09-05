#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 || "$1" != "--target-root" ]]; then
	echo "usage: $0 --target-root <etcd-raft-tree> <clean|mutant>" >&2
	exit 64
fi

target_root=$2
expectation=$3
case "$expectation" in
	clean|mutant) ;;
*)
	echo "expectation must be clean or mutant" >&2
	exit 64
	;;
esac

if [[ ! -d "$target_root" || ! -f "$target_root/go.mod" ]]; then
	echo "target root must be an etcd/raft Go module: $target_root" >&2
	exit 64
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_file="$script_dir/m6_maybe_append_test.go"
temp_root=$(mktemp -d /tmp/consensus-audit-m6-hidden.XXXXXX)
trap 'rm -rf -- "$temp_root"' EXIT

cp -a -- "$target_root" "$temp_root/target"
cp -- "$test_file" "$temp_root/target/hidden_m6_maybe_append_test.go"

set +e
test_output=$(cd "$temp_root/target" && GOCACHE="$temp_root/go-cache" go test -run '^TestHiddenM6MaybeAppendReplacesConflictingEmptyBoundary$' . 2>&1)
test_status=$?
set -e

case "$expectation" in
clean)
	if [[ $test_status -ne 0 ]]; then
		printf '%s\n' "$test_output" >&2
		echo "hidden M6 test unexpectedly failed on clean target" >&2
		exit "$test_status"
	fi
	echo "clean target passed hidden M6 test"
	;;
mutant)
	if [[ $test_status -eq 0 ]]; then
		printf '%s\n' "$test_output" >&2
		echo "hidden M6 test unexpectedly passed on mutant target" >&2
		exit 1
	fi
	printf '%s\n' "$test_output"
	echo "mutant target triggered hidden M6 test as expected"
	;;
esac
