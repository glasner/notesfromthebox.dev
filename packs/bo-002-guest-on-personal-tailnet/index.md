# Give a family member a corner of your personal tailnet (and a headless Mac mini that stays up)

> Replace the allow-all policy with per-user grants plus autogroup:self, limit Funnel to yourself, invite the person so they log in as themselves and own their devices. Then make their Mac mini survive reboots and disconnects: FileVault vs auto-login, pmset sleep/autorestart, Remote Login allowed users, Standalone Tailscale.

- id: `bo-002-guest-on-personal-tailnet` · version 0.1.0 · status private-review · updated 2026-11-15
- not yet tested · review by 2027-01-15 · retracted: false
- default mode: dry-run · digest: `sha256:3bd41361d6cf92feb0651cb1f94dc99f96a70181cf3d134e465707eb76e21f3a`
- canonical: https://notesfromthebox.dev/packs/bo-002-guest-on-personal-tailnet/

## Fit
- goal: Let one more person (a family member, a guest, a contractor) use your tailnet for their own laptop and their own always-on Mac without being able to reach anything else of yours.
- env: Tailscale personal tailnet, policy managed in the admin console
- env: Apple-silicon Mac mini on a current macOS release (26 or later), intended to run headless
- env: Tailscale grants syntax as documented 'Last validated Apr 8, 2026'
- env: macOS 26 or later (FileVault-over-SSH unlock needs 26+)
- needs: You are the tailnet Owner or an Admin
- needs: The family member has their own identity-provider login (e.g. their own email account)
- needs: Physical or screen-sharing access to the Mac with an admin password for the one-time macOS steps
- permission: Edit the tailnet policy file
- permission: Invite users
- permission: macOS admin (sudo) on the Mini, once
- do not use: Organisation tailnets with groups synced from an identity provider: use groups, not this pattern.
- do not use: Tagged devices: autogroup:self does not apply to tagged devices, so a tagged Mini would not be 'theirs'.
- do not use: Laptops: turning FileVault off is a poor trade on anything portable.
- output: A saved policy whose tests prove the isolation, an accepted invite, the Mini logged into Tailscale as the family member, and a Mini that comes back on its own after a reboot or power cut.

## Procedure
_This pack is reference material, not an instruction to change anyone's tailnet. A consuming agent drafts the changes; the owner applies or approves them._

1. [read] Read the current policy: Open the policy file and check for the default allow-all rule (S11): a grant (src '*', dst '*') or an equivalent legacy ACL, plus any nodeAttrs funnel entry targeting autogroup:member.
   expect: You know whether inviting someone today would give them everything.
2. [read] Draft the replacement policy: Start from packs/assets/bo-002-family-policy.hujson: owner → '*', autogroup:member → autogroup:self, Funnel only for the owner, and tests asserting the isolation. Replace the placeholder addresses.
   expect: A draft that names real identities and keeps any existing tag grants your bots need. Add those grants back explicitly; the example has none.
3. [write] Save the policy: Paste into the admin console policy editor and save. The tests block makes the save fail if isolation is wrong (S1).
   expect: Save succeeds; tests pass. Your own devices and bots still reach what they did (check with bo-001 step 4).
   GATE: Tailnet owner. Keep a copy of the old policy text first so it can be restored.
4. [write] Invite the person: Admin console → Users → Invite external users, role Member, by email (S4).
   expect: Invite shows under status:invited until they accept. Unused invites expire after 30 days.
   GATE: Tailnet owner. Inviting adds a billable user if they're active.
5. [write] Give them their own Mac account: On the Mini, create a standard (not admin) account for them. Apple advises against auto-login into an administrator (S7).
   expect: A standard account that is theirs.
   GATE: Owner, at the machine or over Screen Sharing, with the admin password.
6. [write] Decide FileVault vs auto-login: Headless and must come back after a power cut → auto-login needs FileVault off (S6). Keep FileVault → someone has to unlock it after every restart, locally or (macOS 26, untested here) over LAN SSH (S8).
   expect: A written decision. If FileVault goes off: Users & Groups → Automatically log in as → their account.
   GATE: Owner decides; this is a security trade, not a default.
7. [write] Stop it sleeping, restart after power loss: Read first with 'pmset -g', then set system sleep and disk sleep off and auto-restart on.
   `pmset -g; sudo pmset -a sleep 0 disksleep 0 autorestart 1`
   expect: pmset -g shows sleep 0, autorestart 1.
   GATE: Owner with sudo on the Mini. Note the old values from 'pmset -g' for rollback.
8. [write] Sharing allow-lists: System Settings → General → Sharing: add their account to Remote Login's 'Only these users' (S9) and to Screen Sharing if they need it. Remove anyone who shouldn't be there.
   expect: Both lists name exactly the people intended.
   GATE: Owner.
9. [write] Install Standalone Tailscale and log in as them: Install the Standalone variant from Tailscale's package server, not the App Store, and never both (S5). Log out of the admin account. In their session they sign in to Tailscale with their own identity, approve the VPN/system-extension prompt, and enable start at login.
   expect: The Mini appears in the admin console owned by them, not by you.
   GATE: Installer needs the admin password; the Tailscale login is theirs.
10. [probe] Verify isolation from their side: From their laptop or the Mini: tailscale status should list only their own devices; a ping or SSH no-op to one of yours should fail. From your side, run bo-001 step 4 against the Mini.
   expect: They see only theirs; you can still reach the Mini (because the example policy grants you '*').
11. [probe, untested] Verify reboot survival: Restart the Mini (owner-approved), walk away, and from another device wait for it to reappear in tailscale status without anyone touching it.
   expect: Back online in a few minutes with auto-login and Tailscale running in their session.

## Verification
- success: Policy tests pass on save; tailscale status on the family member's device lists only their devices; the Mini is owned by them in the admin console; after an unattended restart the Mini reappears on the tailnet; pmset -g shows sleep 0 and autorestart 1.
- fail: Policy save rejected with a failing test → The draft would break isolation (or your own access). → Read the failing assertion; fix the grant, not the test.
- fail: Family member sees your devices in tailscale status → An allow-all grant or legacy ACL is still present, or they were given an admin role. → Search the policy for '*' in src/dst and check their role on the Users page.
- fail: Mini shows as owned by you → Tailscale on the Mini was logged in with your account, so autogroup:self excludes them. → Log out of Tailscale on the Mini and have them log in as themselves.
- fail: 'Automatically log in as' is greyed out → FileVault is on (S6), the account uses an Apple Account password to log in, or a management profile forbids it. → Check 'fdesetup status'; see step 6.
- fail: Mini drops off the tailnet a minute or so after you stop screen-sharing → Idle system sleep. Our case was sleep 1. → Step 7. Re-test after disconnecting; an active session can hide idle sleep.
- fail: Mini never comes back after a restart → FileVault is waiting for a password, or auto-login is off, so no user session → Standalone Tailscale not running (S5). → Unlock locally (or LAN SSH on macOS 26, untested); revisit step 6.
- fail: Mini rebooted overnight with nobody touching it → Automatic macOS update installed and restarted it. → System Settings → General → Software Update → Automatic updates: turn off automatic macOS installs (security responses are a separate toggle); update on a schedule you choose.
- fail: Tailscale extension won't start after switching variants → Both App Store and Standalone variants present (S5). → Delete Tailscale.app, empty Trash, reboot, install one variant.
- fail: They can't SSH into their own Mini → Their account isn't in Remote Login's allowed list (S9), or they expected Tailscale SSH, which the Standalone variant can't serve. → Step 8; use plain ssh over the tailnet.
- rollback: Policy: paste back the saved previous policy text, or revert the change from the admin console's Configuration logs page (S11). Invite: delete the invite or remove the user on the Users page. pmset: restore the values captured with 'pmset -g' in step 7. FileVault: can be turned back on in System Settings → Privacy & Security (auto-login turns off). Sharing lists: remove the account.
- tested scope: Steps 1–4 and 6–8 were performed on one real tailnet and one Mini in November 2026. Step 9 was pending (the family member's devices had not joined). Steps 10–11, the actual proof of isolation and reboot survival, have not been run. Until they have, treat the verdict as Not yet.

## Sources
- S1 [Syntax reference for the tailnet policy file](https://tailscale.com/kb/1337/policy-syntax) (Tailscale, primary, fetched 2026-11-15, Last validated Apr 8, 2026): autogroup:self selects a user's own devices, doesn't apply to tags; nodeAttrs funnel; tests block rejects a policy save if an assertion fails; tests can't use wildcards.
- S2 [Grants](https://tailscale.com/kb/1324/grants) (Tailscale, primary, fetched 2026-11-15, Last validated Jul 24, 2026): Deny-by-default; grants preferred over legacy ACLs; src/dst/ip structure.
- S3 [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 20, 2026): Enabling Funnel from the CLI adds a nodeAttrs entry that lets every autogroup:member use it by default; admins can restrict it.
- S4 [Invite any user to your tailnet](https://tailscale.com/kb/1271/invite-any-user) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 5, 2026): Invite by email with a chosen role; one account per person; unused invites expire after 30 days; invited users are billed if active; user approval may apply.
- S5 [Three ways to run Tailscale on macOS](https://tailscale.com/kb/1065/macos-variants) (Tailscale, primary, fetched 2026-11-15, Last validated Jan 5, 2026): Standalone variant recommended; neither Standalone nor App Store runs before login; never install both variants.
- S6 [How to log in automatically to a Mac user account](https://support.apple.com/en-us/102316) (Apple, primary, fetched 2026-11-15, Published Date: May 19, 2026): Automatic login is unavailable while FileVault is on.
- S7 [If you don't see a login window when you start your Mac](https://support.apple.com/guide/mac-help/a-login-window-start-mac-mchlp1158/mac) (Apple, primary, fetched 2026-11-15): Don't let automatic login sign in an administrator; auto-login lets anyone with physical access in.
- S8 [Managing FileVault in macOS (Unlock FileVault using SSH)](https://support.apple.com/guide/security/managing-filevault-sec8447f5049/web) (Apple Platform Security, primary, fetched 2026-11-15, Published Date: January 28, 2026): On Apple silicon with macOS 26+, FileVault can be unlocked over SSH after a restart if Remote Login is on and a network connection is available.
- S9 [Allow a remote computer to access your Mac](https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac) (Apple, primary, fetched 2026-11-15): Remote Login 'Allow access for: Only these users' list.
- S10 [pmset(1) reference](https://ss64.com/mac/pmset.html) (SS64 (mirror of the pmset man page), secondary, fetched 2026-11-15): sleep / disksleep / autorestart semantics; 'pmset -g' to read current settings. Cross-check with 'man pmset' on the machine itself.
- S11 [ACL policy examples: Allow all (default ACL)](https://tailscale.com/kb/1192/acl-samples) (Tailscale, primary, fetched 2026-11-15, Last validated Feb 2, 2026): New tailnets start with an allow-all policy; policy changes can be reverted from the Configuration logs page.

## Uncertainty
- Turning FileVault off removes the extra at-rest protection. Apple silicon still encrypts the disk, but without FileVault it unlocks with no password (Apple's FileVault overview). For a Mini that never leaves the house this was our owner's call. For anything portable, don't.
- macOS 26 can unlock FileVault over SSH after a restart (S8). We have not tested it. The Standalone Tailscale client doesn't run before login (S5), so we expect that unlock to work only from the local network, not over the tailnet. That's inferred, not tested.
- Community reports say pre-boot SSH unlock broke or was flaky on some 26.x point releases and on Wi-Fi. Treat it as a bonus, not a plan.
- The 'lock the screen right after auto-login' preference some admins set is not in Apple's public docs; we don't cite a command for it.

License: CC BY 4.0 for text; policy example CC0. Permissions: Dry-run by default. Every write step names who must approve it. The pack itself authorises nothing.
