# multi-releases

Public delivery repository for MultiShift and MultiSwitcher. Private source repositories are not made public. Each approved public release includes the exact corresponding source archive, license and third-party notices.

## Setup

- Enable Pages with GitHub Actions as the build source.
- Create protected `public-delivery` environment. The two source repositories use `multishift-release` / `multiswitcher-release`.
- Install a GitHub App on exactly these three repositories with Contents and Actions read/write. Configure `RELEASE_APP_ID` variable and `RELEASE_APP_PRIVATE_KEY` secret in public-delivery.
- Run `scripts/bootstrap_keys.py` locally once with GitHub admin access. It generates independent Sparkle seeds, configures source public keys and distribution signing secrets, and reuses existing seeds on retry. Back up the local signing folder in encrypted storage. This does not require Apple Developer enrollment.
- Merge the prepared workflows into each source main. Source release builders keep Developer ID/notarization as hard gates; the first pilot disables crash reporting.
- Configure the Next.js console OAuth and GitHub App credentials per its README.

`release-control.yml` serializes all public state changes and Pages deployments. It rebuilds feeds from the current published state, never from the release event's older snapshot. Stable entries have no Sparkle channel; beta entries are marked beta. Every feed and artifact is EdDSA signed. There is no unsigned fallback.

## Recovery

If publication fails after a release state change, use Rebuild in the console. Do not announce success until the workflow and post-deployment checks pass. Withdrawal cannot retract installed files or cached downloads. Ship repaired code with a higher build number; use the previous signed DMG as the documented manual fallback.

`signature`, `notarization`, `gatekeeper`, `functional`, `interface`, `update_a_to_b`, `data_preservation` must all pass against the exact artifact. A source checksum or CI run does not substitute for physical acceptance. Initial signed A/B candidates can be tested in an isolated test feed before public promotion.

## Local checks

`SPARKLE_SIGN_UPDATE=/path/to/sign_update python3 -m unittest discover -s tests -v` checks real EdDSA signing/tamper rejection and combined-channel feed structure. Test keys are ephemeral fixtures and never used for production.
