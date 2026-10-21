# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""A small single agent loop, written to be read.

One model, one context window, one open-ended tool loop:

  * Each turn the model emits a batch of tool calls. The harness runs them in
    parallel and returns the raw results to the same model.
  * Skills are disclosed progressively: only a one-line description of each
    skill sits in the system prompt, and the model loads the full text when a
    task calls for it.
  * Tools can be disclosed progressively too: mark a tool `deferred` and its
    schema is found through tool search instead of sitting in every request.
  * Hard limits live in the harness, not the prompt: a turn budget, a token
    budget that also counts what subagents spend, a cap on calls per batch,
    and a write gate in front of any tool that changes something. The gate is
    required as soon as one tool writes.
  * An optional verifier can check the answer before it is returned. An answer
    it rejects twice is not returned.

This file is a reference, not a framework. Copy the parts your harness is
missing. It needs the `anthropic` package and a model id in KIT_MODEL.
"""

from __future__ import annotations

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

TOOL_SEARCH = {"type": "tool_search_tool_bm25_20251119", "name": "tool_search_tool_bm25"}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    run: Callable[[dict], object]
    writes: bool = False     # changes something outside the conversation, so it goes through the write gate
    deferred: bool = False   # schema is loaded on demand through tool search


@dataclass
class Budget:
    max_turns: int = 25
    max_tokens: int = 400_000   # input plus output, summed over one call to run(), subagents included
    max_batch: int = 16         # tool calls run from one model turn; the rest get an error result


@dataclass
class Result:
    text: str
    stop: str                   # answered | verify_failed | turn_budget | token_budget | refusal | max_tokens
    turns: int
    input_tokens: int           # the loop's own model calls. What tools report through charge() is not in here
    output_tokens: int
    messages: list = field(repr=False, default_factory=list)


def allow_all_writes(tool: Tool, args: dict) -> bool:
    """A write gate that asks nobody. Pass it as `approve` only where no one can be asked, such as an eval."""
    return True


def _tokens(usage) -> tuple[int, int]:
    """Input and output tokens of one response. Cached input counts as input."""
    return ((getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0),
            getattr(usage, "output_tokens", 0) or 0)


def load_skills(directory: str | Path | None) -> dict[str, dict]:
    """Read the name and description from each <directory>/<skill>/SKILL.md."""
    skills: dict[str, dict] = {}
    if not directory:
        return skills
    root = Path(directory).resolve()
    seen: dict[str, Path] = {}
    # KIT_SKILLS_OFF=returns (or a comma list, or "all") hides skills without a code change,
    # for the "does the skill do anything" check after a fold.
    off = {name.strip() for name in os.environ.get("KIT_SKILLS_OFF", "").split(",") if name.strip()}
    for path in sorted(Path(directory).glob("*/SKILL.md")):
        if not path.resolve().is_relative_to(root):   # a symlink must not pull in a file from elsewhere
            raise ValueError(f"Skill {path} points outside {root}.")
        front = re.match(r"---\n(.*?)\n---\n", path.read_text(), re.S)
        meta = dict(re.findall(r"^(\w+):\s*(.+)$", front.group(1), re.M)) if front else {}
        name = meta.get("name", path.parent.name).strip().strip("\"'")
        if name.lower() in seen:   # the name comes from the file, so a new folder could quietly replace a skill
            raise ValueError(f"Two skills are named {name}: {seen[name.lower()]} and {path}.")
        seen[name.lower()] = path
        if name in off or "all" in off:
            continue
        skills[name] = {"description": meta.get("description", ""), "path": path}
    return skills


class Agent:
    def __init__(
        self,
        *,
        system: str,
        tools: list[Tool],
        skills_dir: str | Path | None = None,
        model: str | None = None,
        client=None,
        budget: Budget | None = None,
        approve: Callable[[Tool, dict], bool] | None = None,
        verify: Callable[[str, list], str | None] | None = None,
        on_usage: Callable[[object], None] | None = None,
        cache: bool = True,
    ) -> None:
        self.model = model or os.environ["KIT_MODEL"]
        self.budget = budget or Budget()
        tools = list(tools)
        unguarded = sorted(tool.name for tool in tools if tool.writes)
        if unguarded and approve is None:   # a missing gate must not mean every write runs
            raise ValueError(f"These tools write: {', '.join(unguarded)}. Pass approve=, a callback that confirms "
                             "each write. To run every write unasked, say so with approve=allow_all_writes.")
        self._used = 0                      # tokens counted against the budget in the current run
        self._lock = threading.Lock()
        self._running = threading.Lock()
        self.approve = approve
        self.verify = verify
        self.on_usage = on_usage
        # With caching on, the growing prefix is reread from cache each turn instead of paid for again.
        self.extra = {"cache_control": {"type": "ephemeral"}} if cache else {}
        self.skills = load_skills(skills_dir)
        self.tools = {tool.name: tool for tool in tools}
        self.system = system
        if self.skills:
            self.tools["load_skill"] = Tool(
                name="load_skill",
                description="Load the full instructions for one skill. Do this before work the skill covers.",
                input_schema={"type": "object",
                              "properties": {"name": {"type": "string", "enum": sorted(self.skills)}},
                              "required": ["name"]},
                run=lambda args: self.skills[args["name"]]["path"].read_text(),
            )
            listing = "\n".join(f"- {name}: {skill['description']}" for name, skill in self.skills.items())
            self.system += f"\n\n## Skills\n\nLoad a skill with load_skill before doing work it covers.\n\n{listing}"
        if self.tools and all(tool.deferred for tool in self.tools.values()):
            raise ValueError("At least one tool must not be deferred.")
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client

    # ---- request building ----------------------------------------------
    def _tool_params(self) -> list[dict]:
        params = []
        for tool in self.tools.values():
            param = {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            if tool.deferred:
                param["defer_loading"] = True
            params.append(param)
        if any(tool.deferred for tool in self.tools.values()):
            params.insert(0, TOOL_SEARCH)
        return params

    # ---- budget --------------------------------------------------------
    def charge(self, usage) -> bool:
        """Count tokens spent outside this loop's own model calls against the same budget.
        A tool that runs a subagent calls this with the usage of each subagent response,
        and stops the subagent when it returns False: the budget is spent."""
        with self._lock:
            self._used += sum(_tokens(usage))
            return not self._over_budget()

    def _over_budget(self) -> bool:
        return self._used > self.budget.max_tokens

    # ---- tool execution ------------------------------------------------
    def _execute(self, call) -> dict:
        tool = self.tools.get(call.name)
        if tool is None:
            return self._result(call, f"There is no tool named {call.name}.", error=True)
        if self._over_budget():   # a tool earlier in this batch, such as a subagent, spent what was left
            return self._result(call, "The token budget for this request is spent. This call did not run.", error=True)
        if tool.writes and self.approve is None:   # a tool added after the check in __init__
            return self._result(call, f"{tool.name} changes something and there is no write gate, so it did not run.",
                                error=True)
        if tool.writes and not self.approve(tool, call.input):
            return self._result(call, "The user declined this action. Do not retry it; ask what they want instead.")
        try:
            output = tool.run(call.input)
        except Exception as exc:  # the model can often recover if it sees the error
            return self._result(call, f"{type(exc).__name__}: {exc}", error=True)
        return self._result(call, output if isinstance(output, str) else json.dumps(output, default=str))

    @staticmethod
    def _result(call, content: str, error: bool = False) -> dict:
        result = {"type": "tool_result", "tool_use_id": call.id, "content": content}
        if error:
            result["is_error"] = True
        return result

    def _run_batch(self, calls: list) -> list[dict]:
        """Reads run in parallel. Writes run one at a time, after the reads, in the order the model asked."""
        limit = self.budget.max_batch
        done: dict[str, dict] = {
            call.id: self._result(call, f"Too many tool calls in one turn (the limit is {limit}). This call "
                                        "did not run. Send it again in a later turn if it is still needed.", error=True)
            for call in calls[limit:]}
        reads = [c for c in calls[:limit] if not (self.tools.get(c.name) and self.tools[c.name].writes)]
        if reads:
            with ThreadPoolExecutor(max_workers=min(8, len(reads))) as pool:
                for call, result in zip(reads, pool.map(self._execute, reads)):
                    done[call.id] = result
        for call in calls:
            if call.id not in done:
                done[call.id] = self._execute(call)
        return [done[call.id] for call in calls]   # every result goes back in one user message

    # ---- the loop ------------------------------------------------------
    def run(self, user_text: str, messages: list | None = None) -> Result:
        """Take one user message to an answer. Pass the returned messages back in to continue the conversation.
        An Agent runs one message at a time, because the budget is counted per run. Build one per conversation."""
        if not self._running.acquire(blocking=False):
            raise RuntimeError("This Agent is already in a run. Build one Agent per conversation.")
        try:
            return self._run(user_text, messages if messages is not None else [])
        finally:
            self._running.release()

    def _run(self, user_text: str, messages: list) -> Result:
        messages.append({"role": "user", "content": user_text})
        tokens_in = tokens_out = 0
        self._used = 0
        complaints = 0

        for turn in range(1, self.budget.max_turns + 1):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self.system,
                tools=self._tool_params(),
                messages=messages,
                **self.extra,
            )
            if self.on_usage:
                self.on_usage(response.usage)
            used_in, used_out = _tokens(response.usage)
            tokens_in, tokens_out = tokens_in + used_in, tokens_out + used_out
            self.charge(response.usage)
            messages.append({"role": "assistant", "content": response.content})
            text = "".join(b.text for b in response.content if b.type == "text").strip()

            if response.stop_reason == "pause_turn":   # a server tool, such as tool search, wants another pass
                continue
            if response.stop_reason in ("refusal", "max_tokens", "model_context_window_exceeded"):
                cut_off = [b for b in response.content if b.type == "tool_use"]
                if cut_off:   # every tool call needs a result, or the conversation cannot continue
                    messages.append({"role": "user", "content": [
                        self._result(call, "This call was cut off before it finished and did not run.", error=True)
                        for call in cut_off]})
                if self.verify and text and self.verify(text, messages):
                    text = ""   # a partial answer the verifier rejects is not returned either
                return Result(text, response.stop_reason, turn, tokens_in, tokens_out, messages)
            if response.stop_reason != "tool_use":
                complaint = self.verify(text, messages) if self.verify else None
                if not complaint:
                    return Result(text, "answered", turn, tokens_in, tokens_out, messages)
                complaints += 1
                if complaints > 1:   # one chance to fix it, so it cannot loop forever
                    messages.append({"role": "user", "content": "(Neither answer above was shown to the user.)"})
                    return Result("", "verify_failed", turn, tokens_in, tokens_out, messages)
                messages.append({"role": "user", "content": f"Before this goes to the user: {complaint}"})
                continue

            calls = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "user", "content": self._run_batch(calls)})
            if self._over_budget():
                return Result("", "token_budget", turn, tokens_in, tokens_out, messages)

        return Result("", "turn_budget", self.budget.max_turns, tokens_in, tokens_out, messages)
