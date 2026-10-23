import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())
from models import CybergymSupplyChainAction, CybergymSupplyChainObservation  # noqa: E402

from client import CybergymSupplyChainEnv  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
INDEX = int(sys.argv[2]) if len(sys.argv) > 2 else 0
POC = os.environ.get("SMOKE_POC", "A" * 64)


async def main():
    client = CybergymSupplyChainEnv(base_url=URL)
    await client.connect()
    result = await client.reset(seed=1, split="train", index=INDEX)
    task = result.observation.task_id
    assert task, "no task after reset"
    result = await client.step(CybergymSupplyChainAction(cmd="ls -la"))
    assert result.observation.output, "no output from ls"
    result = await client.step(CybergymSupplyChainAction(cmd="cat challenge.txt"))
    assert "hidden" in result.observation.output.lower(), "challenge text missing"
    result = await client.step(CybergymSupplyChainAction(answer=POC))
    print(f"task={task} reward={result.reward} done={result.done}")
    print((result.observation.output or "")[:300])
    await client.close()
    sys.exit(0 if result.done else 1)


asyncio.run(main())
