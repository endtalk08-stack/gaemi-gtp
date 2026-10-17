# DigitalOcean worker - one-time SSH link

This setup is for the dedicated existing worker only; it does not modify Render or Neon.

## Safe one-time steps
1. Generate a dedicated ED25519 key pair **locally**, not in GitHub or chat:
   `ssh-keygen -t ed25519 -f do_worker_actions -C gaemi-gtp-actions -N ''`
2. Add the **public** key to the DigitalOcean server's deployment user's `~/.ssh/authorized_keys` (not the DigitalOcean account SSH-key list alone). Use restricted server access and keep existing access.
3. Independently verify the server's SSH host key fingerprint, then store its known_hosts line. Do not disable host-key checking.
4. Set repository Actions secrets:
   - `DO_HOST`: verified existing worker public hostname/IP
   - `DO_SSH_USER`: restricted deployment user
   - `DO_SSH_PRIVATE_KEY`: contents of the private key (never commit)
   - `DO_SSH_KNOWN_HOSTS`: verified known_hosts line
5. Run `do-worker-connection-check.yml` manually from its branch in GitHub Actions.
6. Require a passing read-only check before enabling any deployment procedure.

## Guardrails
- No automatic trigger on push.
- No Render modifications or releases.
- No database writes.
- Never upload private SSH keys to repository files or chat.
- Do not assume the local DigitalOcean-only worker source files are in the GitHub repository.
- Take verified backup before any future live worker update.
