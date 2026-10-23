# SPDX-License-Identifier: BSD-3-Clause
"""cybergym_supply_chain: supply-chain incident tasks with server-side verification."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata, State

try:
    from ..models import CybergymSupplyChainAction, CybergymSupplyChainObservation
except ImportError:
    from models import CybergymSupplyChainAction, CybergymSupplyChainObservation

TASKS_DIR = os.environ.get(
    "SUPPLY_CHAIN_TASKS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks"),
)
MAX_STEPS = 200
CMD_TIMEOUT_S = 30
OUTPUT_CAP = 20000
SECRET_FILES = ("answer.sha256", "index.json", "build_history.sh", "build_certs.py")


class CybergymSupplyChainEnvironment(Environment):
    """Submit the corrected module; hidden tests decide the reward."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        with open(os.path.join(TASKS_DIR, "index.json"), encoding="utf-8") as handle:
            self._index = json.load(handle)
        self._tasks = self._index["tasks"]
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task = None
        self._workspace = None
        self._steps_left = 0
        self._done = False
        self._reward = 0.0

    # -- task provider -----------------------------------------------------
    def list_splits(self):
        splits = []
        for task in self._tasks:
            if task["split"] not in splits:
                splits.append(task["split"])
        return splits

    def num_tasks(self, split: str) -> int:
        return sum(1 for task in self._tasks if task["split"] == split)

    def get_task(self, split: str, index: int):
        ids = [task["task_id"] for task in self._tasks if task["split"] == split]
        return {"id": ids[index], "index": index, "split": split}

    # -- environment -------------------------------------------------------
    def reset(self, seed=None, episode_id=None, split=None, index=0, **kwargs):
        split = split or "train"
        candidates = [task for task in self._tasks if task["split"] == split]
        if not candidates:
            raise ValueError(f"unknown split {split!r}")
        index = int(index) % len(candidates)
        self._task = candidates[index]
        self._state = State(episode_id=str(episode_id or uuid4()), step_count=0)
        self._workspace = tempfile.mkdtemp(prefix="oe-ep-", dir="/tmp")
        src = os.path.join(TASKS_DIR, self._task["task_id"])
        for name in sorted(os.listdir(src)):
            if name in SECRET_FILES or name == "__pycache__":
                continue
            path = os.path.join(src, name)
            dest = os.path.join(self._workspace, name)
            if os.path.isdir(path):
                shutil.copytree(path, dest)
            elif os.path.isfile(path):
                shutil.copy2(path, dest)
                if name == "ovhctl":
                    os.chmod(dest, 0o755)
        self._steps_left = MAX_STEPS
        self._done = False
        self._reward = 0.0
        return CybergymSupplyChainObservation(
            task_id=self._task["task_id"],
            challenge=self._read_challenge(),
            output="",
            message="Episode ready. Explore with cmd; finish with answer (the full module source).",
            steps_left=self._steps_left,
            done=False,
            reward=0.0,
        )

    def _read_challenge(self):
        path = os.path.join(self._workspace, "challenge.txt")
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        return ""

    def _grade(self, answer: str):
        digest_path = os.path.join(TASKS_DIR, self._task["task_id"], "answer.sha256")
        with open(digest_path, encoding="utf-8") as handle:
            expected = handle.read().strip()
        digest = hashlib.sha256(answer.encode("utf-8", "replace")).hexdigest()
        ok = digest == expected
        return (1.0 if ok else 0.0), f"answer check: {'correct' if ok else 'incorrect'}\n"

    def step(self, action: CybergymSupplyChainAction, timeout_s=None, **kwargs):
        if self._done or self._workspace is None:
            return CybergymSupplyChainObservation(
                task_id=self._task["task_id"] if self._task else "",
                challenge="",
                output="The episode has ended. Reset to start another task.",
                message="ended",
                steps_left=0,
                done=True,
                reward=self._reward,
            )
        self._state.step_count += 1

        if action.answer:
            self._reward, text = self._grade(action.answer)
            self._done = True
            self._steps_left = 0
            return CybergymSupplyChainObservation(
                task_id=self._task["task_id"],
                challenge="",
                output=text,
                message="final answer graded",
                steps_left=0,
                done=True,
                reward=self._reward,
            )

        command = (action.cmd or "").strip()
        if command == "done":
            self._done = True
            self._steps_left = 0
            return CybergymSupplyChainObservation(
                task_id=self._task["task_id"],
                challenge="",
                output="Episode closed without a final answer (reward 0).",
                message="gave up",
                steps_left=0,
                done=True,
                reward=0.0,
            )

        self._steps_left -= 1
        try:
            proc = subprocess.run(
                ["/bin/sh", "-c", command],
                cwd=self._workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=CMD_TIMEOUT_S,
            )
            output = proc.stdout.decode("utf-8", "replace")
            if proc.returncode != 0:
                output += f"\n[exit {proc.returncode}]"
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or b"").decode("utf-8", "replace")) + "\n[timeout]"
        except Exception as exc:  # noqa: BLE001
            output = f"[error] {type(exc).__name__}: {exc}"

        if self._steps_left <= 0:
            self._done = True
            output += "\n[step budget exhausted; episode closed with reward 0]"

        return CybergymSupplyChainObservation(
            task_id=self._task["task_id"],
            challenge="",
            output=output[:OUTPUT_CAP],
            message="",
            steps_left=self._steps_left,
            done=self._done,
            reward=self._reward,
        )

    @property
    def state(self) -> State:
        return self._state

    def get_metadata(self) -> EnvironmentMetadata:
        return EnvironmentMetadata(
            name="cybergym_supply_chain",
            description="Supply-chain incident tasks with server-side answer verification.",
            version="1.0.0",
        )

    def close(self):
        if self._workspace and os.path.isdir(self._workspace):
            shutil.rmtree(self._workspace, ignore_errors=True)
