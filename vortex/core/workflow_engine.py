# vortex/core/workflow_engine.py

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional


@dataclass
class WorkflowStep:
    type: str
    params: Dict[str, Any]


@dataclass
class Workflow:
    name: str
    description: str
    steps: List[WorkflowStep]


class WorkflowEngine:
    """
    Very simple workflow engine for VORTEX.

    - Workflows are JSON files in data/workflows/*.json
    - Each file looks like:

      {
        "name": "focus_mode",
        "description": "Close distractions and open coding tools",
        "steps": [
          {"type": "say", "text": "Entering focus mode."},
          {"type": "close_app", "app": "chrome"},
          {"type": "open_app", "app": "code"},
          {"type": "note", "text": "Focus session started.", "category": "workflow"}
        ]
      }

    - Supported step types (for now):
      - say         -> TTS + console message
      - sleep       -> wait N seconds
      - open_app    -> reuse controller's open app logic
      - close_app   -> reuse controller's close app logic
      - note        -> store a memory note
    """

    def __init__(self, controller, data_dir: Path, logger=None):
        self.controller = controller
        self.logger = logger or getattr(controller, "logger", None)
        self.data_dir = Path(data_dir)
        self.workflows_dir = self.data_dir / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

        self.workflows: Dict[str, Workflow] = {}
        self._load_all()

        # If there are no workflows yet, create a sample one
        if not self.workflows:
            self._create_sample_workflow()
            self._load_all()

    # ---------- loading ----------

    def _load_all(self):
        self.workflows.clear()
        for path in self.workflows_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                name = raw.get("name") or path.stem
                description = raw.get("description", "")
                steps: List[WorkflowStep] = []
                for s in raw.get("steps", []):
                    stype = s.get("type")
                    if not stype:
                        continue
                    params = {k: v for k, v in s.items() if k != "type"}
                    steps.append(WorkflowStep(type=stype, params=params))

                wf = Workflow(name=name, description=description, steps=steps)
                key = self._key_for_name(name)
                self.workflows[key] = wf
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to load workflow from {path}: {e}")

    def _create_sample_workflow(self):
        """
        Creates a simple example workflow: focus_mode.json
        Only created if there are no workflows yet.
        """
        sample = {
            "name": "focus_mode",
            "description": "Close distractions and open coding tools for deep work.",
            "steps": [
                {"type": "say", "text": "Entering focus mode. Closing distractions and opening your tools."},
                {"type": "close_app", "app": "chrome"},
                {"type": "close_app", "app": "edge"},
                {"type": "sleep", "seconds": 1},
                {"type": "open_app", "app": "code"},
                {"type": "note", "text": "Focus session started by VORTEX.", "category": "workflow"},
                {"type": "say", "text": "You're all set. Let's get some serious work done."}
            ],
        }

        path = self.workflows_dir / "focus_mode.json"
        try:
            path.write_text(json.dumps(sample, indent=2), encoding="utf-8")
            if self.logger:
                self.logger.info(f"Created sample workflow at {path}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create sample workflow: {e}")

    # ---------- public API ----------

    def list_workflows(self) -> List[Workflow]:
        return list(self.workflows.values())

    def run_workflow(self, name: str) -> bool:
        """
        Starts executing workflow in a background thread.
        Returns True if workflow exists, False otherwise.
        """
        key = self._key_for_name(name)
        wf = self.workflows.get(key)
        if wf is None:
            return False

        thread = threading.Thread(target=self._run_workflow_thread, args=(wf,), daemon=True)
        thread.start()
        return True

    # ---------- execution ----------

    def _run_workflow_thread(self, wf: Workflow):
        if self.logger:
            self.logger.info(f"Running workflow: {wf.name}")

        self.controller._emit_system_message(
            f"Starting workflow '{wf.name}'.",
            speak=False,
        )

        for step in wf.steps:
            try:
                self._execute_step(step, wf)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in workflow '{wf.name}' step {step.type}: {e}")

        self.controller._emit_system_message(
            f"Workflow '{wf.name}' completed.",
            speak=False,
        )

    def _execute_step(self, step: WorkflowStep, wf: Workflow):
        t = step.type.lower()
        p = step.params

        if t == "say":
            text = p.get("text", "")
            if text:
                self.controller._emit_system_message(text, speak=True)

        elif t == "sleep":
            seconds = float(p.get("seconds", 1.0))
            time.sleep(max(0.0, seconds))

        elif t == "open_app":
            app = p.get("app")
            if app:
                msg = p.get("message", f"Opening {app} for you.")
                self.controller._handle_open_app(app, msg, uses_context=False)

        elif t == "close_app":
            app = p.get("app")
            if app:
                msg = p.get("message", f"Closing {app} for you.")
                self.controller._handle_close_app(app, msg, uses_context=False)

        elif t == "note":
            text = p.get("text")
            if text:
                category = p.get("category", "workflow")
                self.controller.memory.add(text, category=category)
                self.controller._refresh_memory_panel()

        else:
            if self.logger:
                self.logger.warning(f"Workflow '{wf.name}': unknown step type '{step.type}'")

    # ---------- helpers ----------

    @staticmethod
    def _key_for_name(name: str) -> str:
        return name.strip().lower().replace(" ", "_")
