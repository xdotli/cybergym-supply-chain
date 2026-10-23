"""The organizer's admission probe: play the submission's example_actions (and
finish_action) against every task and require a terminal reward in [0, 1].

Prints one JSON line: {"env": url, "tasks": [{"task_id", "terminal", "reward"}...],
"schema_match": bool, "verdict": "validated"|"rejected"}.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from models import CybergymSupplyChainAction, CybergymSupplyChainObservation  # noqa: E402

from client import CybergymSupplyChainEnv  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
import os as _os
EXAMPLES = [{"cmd": "ls -la"}, {"cmd": "cat challenge.txt"}, {"answer": _os.environ.get("WARMUP_ANSWER", "")}]
FINISH = {"cmd": "done"}
TASKS = [t["task_id"] for t in json.load(open(os.path.join(os.getcwd(), "server/tasks/index.json")))["tasks"]]


async def probe(client, task_id, index):
    await client.reset(seed=3, split="train", index=index)
    terminal, reward = False, 0.0
    for action in EXAMPLES:
        result = await client.step(CybergymSupplyChainAction(**action))
        terminal, reward = result.done, result.reward or 0.0
        if terminal:
            break
    if not terminal:
        result = await client.step(CybergymSupplyChainAction(**FINISH))
        terminal, reward = result.done, result.reward or 0.0
    ok = terminal and 0.0 <= reward <= 1.0
    print(f"task {task_id}: terminal={terminal} reward={reward} -> {'ok' if ok else 'FAIL'}")
    return {"task_id": task_id, "terminal": terminal, "reward": reward, "ok": ok}


async def main():
    client = CybergymSupplyChainEnv(base_url=URL)
    await client.connect()
    rows = []
    for index, task_id in enumerate(TASKS):
        rows.append(await probe(client, task_id, index))
    await client.close()
    verdict = "validated" if all(row["ok"] for row in rows) else "rejected"
    print(json.dumps({"env": URL, "tasks": rows, "verdict": verdict}))


asyncio.run(main())
