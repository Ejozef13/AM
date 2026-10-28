# Docker access while AM stays open

Use the managed entry point:

```bash
python am.py on --diagnostics
```

Keep its launch terminal open. If Docker already works directly (including an
existing rootless setup), AM uses that access and starts no sudo refresher.
Otherwise startup asks for the normal sudo authorization once and checks Docker.

`sudo_session.py` then runs `sudo -n -v` every 30 seconds while this AM process
is alive. It uses the same controlling terminal and parent PID as its Docker
calls. Normal idle time should no longer let an otherwise valid credential
expire during study. It also runs during model generation and container cleanup.
No password is stored, sent to the browser, or read by application code.

## Sleep, revocation, and renewal

Suspending the computer, manually invalidating sudo, or an administrator changing
policy can invalidate authorization despite periodic refresh. When that happens,
AM asks in the launch terminal using sudo's ordinary password prompt. A failed
Docker request wakes the refresher immediately rather than waiting for its next
periodic check. Enter the
password there, then retry the browser operation. The website, editor contents,
and saved sessions stay open; restarting is unnecessary.

If a prompt is canceled, AM does not repeat it continuously. The existing manual
recovery remains available without a restart: in the launch terminal press
Ctrl+Z, run `sudo -v`, then `fg` and retry. Another terminal may have a different
sudo timestamp. With no controlling terminal, AM cannot display an interactive
password prompt; use an interactive launch for this sudo-based mode.

AM respects the machine's sudo policy. An administrator who requires a password
for every command (for example `timestamp_timeout=0`) cannot be bypassed by
credential refresh. For unattended operation without sudo, use a properly
configured rootless Docker installation and prepare AM's runtime images there.
That is a separate installation choice; AM does not change your Docker context,
group memberships, socket permissions, or global sudo rules automatically.

## Stop

Ctrl+C in the launch terminal or `python am.py off` from another terminal stops
the managed app. It first cancels active work and cleans up containers, then
unloads the selected models and stops the credential refresher. A pending sudo
renewal prompt is canceled too. Other services remain available. AM does not
invalidate credentials another application may still be using; after refresh
stops, the normal sudo timeout applies.

`practice_web.py` is the lower-level server entry point; it does not own this
managed credential lifecycle. Use `am.py on` for all-day desktop practice.
