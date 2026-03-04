# Noa — Docker Dev Environment

Isolated development container for working on Noa. Runs as non-root with a read-only root filesystem and no access to host system paths.

## Quick Start

```bash
# Build the image
docker compose -f docker-compose.dev.yml build

# Start an interactive shell
docker compose -f docker-compose.dev.yml run --rm dev bash

# Start Claude Code directly
ANTHROPIC_API_KEY="sk-ant-..." docker compose -f docker-compose.dev.yml run --rm dev claude
```

> **API Key:** Der Key wird per Environment-Variable übergeben und landet nur im laufenden Container-Prozess — nie im Image oder Repo. Alternativ eine `.env`-Datei anlegen (muss in `.gitignore` stehen):
>
> ```
> # .env
> ANTHROPIC_API_KEY=sk-ant-...
> ```

## Verify Isolation

Inside the container, confirm only the expected mounts exist:

```bash
# Should show repo contents
ls /workspace

# Should be empty (or contain .gitkeep)
ls /artifacts

# Should fail or show nothing sensitive
ls /root        # permission denied (running as devuser)
ls /home        # only devuser home, no host files
mount | grep -v tmpfs  # no host paths beyond /workspace and /artifacts
whoami          # devuser (not root)
```

## Installing Dependencies

This repo currently has no `requirements.txt` or `pyproject.toml`. When dependencies are added, install them inside the container:

```bash
pip install -r requirements.txt
# or
pip install -e .
```

Since the root filesystem is read-only, pip installs go to the user's home directory (`~/.local`). For persistent installs, add them to the Dockerfile.

## DO NOT

- **Do not mount `$HOME`** or any parent directory beyond the repo root.
- **Do not mount `/var/run/docker.sock`** — no Docker-in-Docker.
- **Do not use `--privileged`** or `--network=host`.
- **Do not put secrets in this repo** — no API keys, no SSH keys, no credentials.
- **Do not mount `~/.ssh`, `~/.aws`**, keychains, or any credential stores.
