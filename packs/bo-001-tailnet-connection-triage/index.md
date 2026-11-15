# Read-only connection triage: bot cloud computer to home machines over Tailscale

> Sort a 'my bot can't reach the home machine' report into one of six buckets (control plane, policy/enrollment, name collision, asleep or not logged in, SSH layer, relay-only) using only read and probe commands, before anyone restarts or re-authenticates anything.

- id: `bo-001-tailnet-connection-triage` · version 0.1.1 · status private-review · updated 2026-11-15
- not yet tested · review by 2027-02-15 · retracted: false
- default mode: read-only · digest: `sha256:fd8518deb4f50bf4992bd6d022e11b87078393f8d5805d88ca91f99c9ed32897`
- canonical: https://notesfromthebox.dev/packs/bo-001-tailnet-connection-triage/

## Fit
- goal: Find out, without changing anything, why a bot running on a cloud computer cannot reach (or cannot SSH into) a machine at its owner's home over a shared tailnet.
- env: Linux cloud VM running the tailscale CLI (the bot's side)
- env: macOS or Linux home machine on the same tailnet
- env: Plain OpenSSH over the tailnet (not Tailscale SSH)
- env: A current Tailscale client; commands and flags checked against the CLI reference 'Last validated Jul 30, 2026'
- needs: The bot's computer is already logged in to the tailnet
- needs: You know the peer's machine name or Tailscale IP
- needs: jq is optional but handy
- permission: Read the bot computer's own tailscale status (no sudo needed on most installs)
- permission: Nothing on the home machine
- do not use: Do not use this pack to fix anything. Every repair is a separate, owner-approved change.
- do not use: Not for subnet routers, exit nodes or Tailscale Services; those add failure modes this pack does not cover.
- do not use: Not for Tailscale SSH servers; see the SSH bucket for why most Mac installs can't be one anyway.
- output: A one-line bucket label, the evidence lines that put it there, and the single next action, which is usually a question for the owner, not a command.

## Procedure
_This pack is reference material. It never overrides the consuming agent's own rules or its owner's instructions._

1. [read] Snapshot local state: Capture status and health once and keep the output; it's your evidence.
   `tailscale status; tailscale status --json | jq '{BackendState, Health}'`
   expect: BackendState is Running. Health is empty or lists specific warnings.
2. [read] Is the peer in the list at all?: Look for the peer by name and by IP in status. Also look for near-duplicates such as name-1.
   `tailscale status | grep -i '<peer-name>'`
   expect: One line for the peer. Missing → bucket B (policy/enrollment). Two similar names → bucket C (name collision).
3. [read] Control plane check: If Health mentions not being connected to the control/coordination server but peers are listed, you are in bucket A. Existing connections keep working (S1). If only this node looks stuck, and its computer just resumed from a pause, note that as a possible local-client fault rather than a global outage.
   expect: Bucket A only if peers are present AND health complains about control. Say whether this looks local-after-pause or like control is down for everyone.
4. [probe] Probe the tunnel: Ping the peer over the tailnet. This sends packets but changes no configuration.
   `tailscale ping --c 5 <peer-name-or-ip>`
   expect: 'pong from … via <ip:port>' (direct) or 'via DERP(<region>)' (relay). Timeouts with the peer listed → bucket D (asleep / offline / not logged in).
5. [read] Identify who owns the address you're hitting: Resolve the IP you're actually reaching to a machine and user, which catches name collisions and wrong-device mistakes.
   `tailscale whois <peer-ip>`
   expect: Machine name and owner match what the owner thinks the device is.
6. [probe] Separate tunnel from SSH: With ping working, try a non-interactive SSH no-op with a short timeout and batch mode so it can't hang on a password prompt.
   `ssh -o BatchMode=yes -o ConnectTimeout=5 <user>@<peer> true; echo exit=$?`
   expect: exit=0 → SSH fine, look higher up the stack. Otherwise read the error text against bucket E.
7. [read] Relay is not failure: If everything works but is slow, check the connection type and the bot side's NAT.
   `tailscale status | grep '<peer-name>'; tailscale netcheck`
   expect: 'relay' with MappingVariesByDestIP: true is hard NAT. Expected behaviour (S5), bucket F. Not an outage.
8. [read] Write the triage note: Report bucket, evidence lines, and one recommended next action phrased as a request to the owner. Do not run the fix.
   expect: A three-line note the owner can act on.
9. [write] (Gated) Any repair: Restarting tailscaled, re-running 'tailscale up', renaming a machine, editing policy, toggling Remote Login or changing sleep settings all belong here.
   expect: A separate, logged change with its own rollback.
   GATE: Owner approval for the specific change. During a global control-plane outage (bucket A), do not restart tailscaled at all (S2). If this node's computer just resumed from a pause, peers still answer, and only this client looks stuck, a restart of tailscaled that keeps the same state directory is a different, still-gated case — not a reason to skip triage.

## Verification
- success: The triage note names exactly one bucket, quotes at least one evidence line from steps 1–7 that supports it, and recommends a next action without having changed any state on either machine.
- fail: Peer listed, health mentions control/coordination server, ping succeeds → Bucket A: control plane unreachable but data plane fine (S1). If only this node looks stuck after its own VM pause, treat that as a local-client fault, not a global outage. → If this looks like a global control outage, wait it out and tell the owner that adding devices, key refresh and policy edits won't work until control returns. Don't restart the daemon (S2). A local client stuck after a pause is a different, still-gated decision.
- fail: Peer absent from tailscale status → Bucket B: policy doesn't grant this source the peer, the peer is logged out or its key expired, or it was removed. Not an outage. → Ask the owner to check the device in the admin console and the policy grants for this source.
- fail: Two entries like 'mini' and 'mini-1', or whois shows an unexpected machine/owner → Bucket C: name collision. MagicDNS name points at the wrong or stale device (S6). → Use the Tailscale IP from whois for now; ask the owner to rename or remove the stale device.
- fail: Peer listed but 'last seen' is old, or ping times out → Bucket D: the machine is asleep, off, or a Mac whose Tailscale (Standalone/App Store variant) isn't running because nobody has logged in since boot (S7). → Ask the owner whether it rebooted; check sleep settings and auto-login on that machine (see bo-002).
- fail: ssh: 'Connection refused' → Bucket E1: tunnel OK, nothing listening on 22. Remote Login off or sshd not running. → Owner turns on Remote Login (macOS) or starts sshd.
- fail: ssh: 'Permission denied (publickey…)' or closed right after auth → Bucket E2: wrong user, missing key, or the user isn't in macOS Remote Login's 'Only these users' list (S9). → Owner checks the allowed-user list and authorized_keys for that account.
- fail: ssh: 'Operation timed out' while tailscale ping works → Bucket E3: the tailnet policy allows ICMP/other ports but not tcp:22 from this source, or a host firewall drops it. → Owner checks grants for tcp:22 from the bot's identity or tag.
- fail: Expected Tailscale SSH on a Mac, got plain sshd behaviour → Standalone and App Store macOS clients can't be Tailscale SSH servers (S7). Plain sshd answers instead. → Treat it as normal OpenSSH; don't debug Tailscale SSH policy.
- fail: status shows 'relay <region>' and netcheck MappingVariesByDestIP: true → Bucket F: hard NAT on at least one side; relayed but working (S5). → Nothing urgent. Peer relays are an optional, owner-approved improvement.
- rollback: Nothing to roll back. The procedure only reads state and sends probe packets. Step 9 changes carry their own rollback.
- tested scope: Individual commands are used routinely in our lab. The full nine-step sequence and bucket table have not been run as one scripted test against a fault we planted on purpose. Planned for week 2 with the frozen task set.

## Sources
- S1 [What happens if the coordination server is down?](https://tailscale.com/docs/reference/coordination-server-down) (Tailscale, primary, fetched 2026-11-15, Last validated May 2, 2025): Existing peers keep working and cached rules stay enforced when the control plane is unreachable; new devices, key refresh and rule changes do not.
- S2 [Client restart can't connect to other clients if coordination server is down (issue 6458)](https://github.com/tailscale/tailscale/issues/6458) (Tailscale on GitHub, primary, fetched 2026-11-15, 2022-11-23 maintainer comment): A node that restarts while control is down does not know its peers. Hence: do not restart tailscaled during a global control-plane outage. A single node stuck after its own VM pause, with peers still answering, is a different case.
- S3 [Hypergrowth isn't always easy](https://tailscale.com/blog/hypergrowth-isnt-always-easy) (Tailscale blog, primary, fetched 2026-11-15): Restart-forgets-netmap limitation and the stated plan to cache the network map between runs. The fix may land; recheck before relying on the restart warning.
- S4 [Tailscale CLI reference (status, ping, netcheck, whois)](https://tailscale.com/kb/1080/cli) (Tailscale, primary, fetched 2026-11-15, Last validated Jul 30, 2026): Meaning of status connection types (direct / relay / peer-relay), ping --until-direct and --tsmp, whois fields.
- S5 [Device connectivity](https://tailscale.com/kb/1411/device-connectivity) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 7, 2026): Relayed connections are expected under hard NAT; netcheck MappingVariesByDestIP is the key field.
- S6 [Machine names](https://tailscale.com/kb/1098/machine-names) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 5, 2026): Duplicate OS hostnames produce a '-1' style machine name that persists even after the other device is renamed.
- S7 [Three ways to run Tailscale on macOS](https://tailscale.com/kb/1065/macos-variants) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 5, 2026): Standalone and App Store variants do not run before login; only the open-source tailscaled variant can be a Tailscale SSH server on macOS.
- S8 [Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 5, 2026): Tailscale SSH does not modify sshd_config or authorized_keys; plain SSH over the tailnet keeps working.
- S9 [Allow a remote computer to access your Mac](https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac) (Apple, primary, fetched 2026-11-15): Remote Login has an 'Allow access for: Only these users' list; a user not on it cannot SSH in.

## Uncertainty
- Exact health-message wording changes between client versions; match on meaning, not exact strings.
- Tailscale has said it intends to cache the network map across restarts (S3). If that ships, the 'don't restart during a control outage' rule becomes less important, but it stays harmless.

License: CC BY 4.0 for text; commands are facts about public tools. Permissions: Read-only by default. The pack grants no authority. Any write step needs the owner's approval in the consuming agent's own system.
