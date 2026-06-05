# Experiment registry — the pre-registration ledger

One line per protocol version. The **git commit SHA** of the protocol file is the binding seal:
it proves the protocol was fixed *before* the sealed TEST origins were scored. Verify with
`git log --diff-filter=A -- experiments/protocol_vN.yaml` (when the file was added) vs the
`experiment_ledger` row carrying `is_test_reveal=1` (when TEST was scored). The add must precede
the reveal.

| Protocol | Registered | Scope | Sealed TEST origins | Commit SHA | TEST revealed? |
|---|---|---|---|---|---|
| [v1](protocol_v1.yaml) | 2026-06-05 | Frozen detector → gain-of-cohort-share, OpenAlex universe | 2018, 2020 | _(set on commit)_ | not yet |

## Rules
- A protocol is **immutable once committed**. To change a knob, the universe, the label, or the
  splits, write `protocol_v2.yaml` with **new, later** test origins — never re-open an old seal.
- The headline number is always `lift_declustered` on the sealed TEST, with its block-permutation
  `p_block` **deflated** by that protocol's `n_configs_declared`.
- A null result is logged here as faithfully as a positive one. The point of the seal is that we
  cannot quietly discard the runs we didn't like.
