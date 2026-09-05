// This file is evaluator-only. The runner copies it into a temporary target
// copy after an audit; it must never be placed in an LLM-visible TARGET_ROOT.
package raft

import (
	"bytes"
	"testing"

	pb "go.etcd.io/raft/v3/raftpb"
)

// TestHiddenM6MaybeAppendReplacesConflictingEmptyBoundary verifies the local
// M6 mechanism. A follower has a stale entry at index 2. A new leader sends a
// matching-prefix append containing its empty no-op at index 2 followed by a
// proposal at index 3. Correct conflict resolution replaces index 2 before
// appending index 3. M6 skips index 2 from findConflict and leaves it intact.
func TestHiddenM6MaybeAppendReplacesConflictingEmptyBoundary(t *testing.T) {
	storage := NewMemoryStorage()
	if err := storage.Append([]pb.Entry{
		{Index: 1, Term: 1},
		{Index: 2, Term: 1, Data: []byte("old")},
	}); err != nil {
		t.Fatalf("append follower entries: %v", err)
	}
	follower := newLog(storage, raftLogger)
	follower.committed = 1

	incoming := []pb.Entry{
		{Index: 2, Term: 2},
		{Index: 3, Term: 2, Data: []byte("proposal")},
	}
	appendSlice := logSlice{
		term:    2,
		prev:    entryID{index: 1, term: 1},
		entries: incoming,
	}
	if err := appendSlice.valid(); err != nil {
		t.Fatalf("invalid test append slice: %v", err)
	}

	lastIndex, accepted := follower.maybeAppend(appendSlice, 1)
	if !accepted || lastIndex != 3 {
		t.Fatalf("maybeAppend accepted=%v lastIndex=%d, want true/3", accepted, lastIndex)
	}
	got, err := follower.entries(1, noLimit)
	if err != nil {
		t.Fatalf("read resulting log: %v", err)
	}
	if len(got) != len(incoming)+1 {
		t.Fatalf("resulting log length=%d, want %d: %+v", len(got), len(incoming)+1, got)
	}
	for offset, want := range incoming {
		actual := got[offset+1]
		if actual.Index != want.Index || actual.Term != want.Term || !bytes.Equal(actual.Data, want.Data) {
			t.Fatalf(
				"index %d remained inconsistent: got {Index:%d Term:%d Data:%q}, want leader entry {Index:%d Term:%d Data:%q}",
				want.Index,
				actual.Index,
				actual.Term,
				actual.Data,
				want.Index,
				want.Term,
				want.Data,
			)
		}
	}
}
