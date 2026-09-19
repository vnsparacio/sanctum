# Quickstart

Run `make deps`, `make build`, `make test`, `make audit`, `make setup`, then `make doctor` from the source root. Dependencies are pinned; setup requires the reviewed source and runtime hashes to match. An ordinary source download works before any Git remote exists.

The default prefix is `.local/`, excluded from publication. To choose another private directory, pass `PREFIX=/absolute/private/directory` to each Make command. Use an empty directory with mode 0700. Setup is idempotent; changed receipts/configuration are refused instead of overwritten. Paths with quotes/backslashes are currently rejected.

`make up` starts the isolated candidate gateway on loopback port 28789. It does not start an inference server. Local MLX defaults to port 28080, so a currently running production server is not adopted accidentally. Run the local model component only after following [installation](installation.md). `make status`, `make logs`, `make down` and `make uninstall` operate on the candidate; uninstall preserves state.

No paid provider, personal source or browser action is exercised by offline verification. Optional integrations and host requirements are explicit rather than inferred from this Mac's existing installation.

After setup, optional host runtimes have explicit isolated installers:

```sh
.venv/bin/python scripts/bootstrap.py mlx --prefix "$PWD/.local"
.venv/bin/python scripts/bootstrap.py webui --prefix "$PWD/.local"
```

Then use the component commands in [installation](installation.md). Runtime directories are not overwritten. A source-only build does not install model weights or prove live personal/GPU integration. See the historical **READY WITH DOCUMENTED EXCEPTIONS** [qualification](../history/v1/qualification.md) before deployment.
