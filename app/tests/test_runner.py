"""Tests for the Runner Agent's tools and the workflow's Runner node.

No model or network calls: a scripted chat model drives the real tools and
OpenRouter responses are faked.

Run from the app/ directory:

    python -m unittest discover -s tests -t .
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend import workflow
from backend.agents import runner
from tests.workers import MODEL, TEST_CASES, FakeCompletion


SECOND_MODEL = {
    "name": "Second model",
    "provider": "Test",
    "model_id": "test/second-model",
}

# Long output with quotes, newlines and non-ASCII text, the kind of
# content an LLM fails to copy back exactly as a tool argument
LONG_OUTPUT = 'سياسة الإرجاع: "30 يومًا"\n- Step with \\ and "quotes"\n' * 200

STATE = {
    "user_request": "Test project",
    "retry_count": 0,
    "retry_required": False,
    "selected_model": None,
}


class ScriptedChatModel(GenericFakeChatModel):
    """Replays fixed messages. Tool binding is a no-op."""

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(name: str, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": {}, "id": call_id}],
    )


def scripted_runner_agent(*tool_names: str):
    messages = [
        tool_call(name, f"call_{index}")
        for index, name in enumerate(tool_names)
    ]
    messages.append(
        AIMessage(content="Benchmark completed and saved to runner_results.json")
    )

    return create_agent(
        model=ScriptedChatModel(messages=iter(messages)),
        tools=[
            runner.load_runner_inputs,
            runner.run_models_parallel,
            runner.save_runner_results,
        ],
        system_prompt=runner.RUNNER_PROMPT,
    )


def fake_post(url, headers, json, timeout):
    if json["model"] == SECOND_MODEL["model_id"] and json["messages"][0][
        "content"
    ] == TEST_CASES[0]["prompt"]:
        raise requests.HTTPError("429 Too Many Requests")

    return FakeCompletion(LONG_OUTPUT)


class RunnerNodeTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.data_dir = Path(temp_dir.name)

        for module in (runner, workflow):
            patcher = mock.patch.object(module, "DATA_DIR", self.data_dir)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher = mock.patch.object(runner.requests, "post", side_effect=fake_post)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.write_json("evaluation_plan.json", {
            "project_name": "Test project",
            "project_type": "test",
            "project_goal": "test",
            "evaluation_criteria": ["Accuracy"],
            "candidate_models": [MODEL, SECOND_MODEL],
        })
        self.write_json("benchmark.json", {
            "project_name": "Test project",
            "test_cases": TEST_CASES,
        })

    def write_json(self, name: str, data: dict) -> None:
        (self.data_dir / name).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def run_node(self, agent):
        captured = {}
        original_invoke = agent.invoke

        def invoke(*args, **kwargs):
            captured["result"] = original_invoke(*args, **kwargs)
            return captured["result"]

        with mock.patch.object(workflow, "runner_agent", agent), \
                mock.patch.object(agent, "invoke", side_effect=invoke):
            workflow.runner_node(STATE)

        return captured["result"]["messages"]

    def test_results_are_saved_without_the_model_copying_them(self):
        """Regression: runner_results.json was missing after the Runner ran.

        save_runner_results used to take the full results as an argument,
        so the LLM had to reproduce them. Any change to that text failed
        validation, ToolNode returned the error to the LLM, and the
        workflow raised "Runner failed to save runner_results.json".
        """

        # Neither tool takes data the model has to copy
        self.assertEqual(runner.run_models_parallel.args, {})
        self.assertEqual(runner.save_runner_results.args, {})

        messages = self.run_node(
            scripted_runner_agent(
                "load_runner_inputs",
                "run_models_parallel",
                "save_runner_results",
            )
        )

        tool_messages = {
            message.name: message
            for message in messages
            if isinstance(message, ToolMessage)
        }
        for message in tool_messages.values():
            self.assertNotEqual(message.status, "error", message.content)

        # The model outputs never reach the LLM's context
        self.assertNotIn(
            "سياسة", tool_messages["run_models_parallel"].content
        )

        results = json.loads(
            (self.data_dir / "runner_results.json").read_text("utf-8")
        )
        self.assertEqual(results["project_name"], "Test project")

        models = {model["model_id"]: model for model in results["models"]}
        self.assertEqual(
            set(models), {MODEL["model_id"], SECOND_MODEL["model_id"]}
        )

        first = models[MODEL["model_id"]]
        self.assertEqual(first["results"][0]["output"], LONG_OUTPUT)
        self.assertEqual(first["summary"]["successful_tests"], 3)
        self.assertEqual(first["summary"]["failed_tests"], 0)
        self.assertEqual(first["summary"]["total_input_tokens"], 30)
        self.assertEqual(first["summary"]["total_output_tokens"], 60)
        self.assertEqual(first["summary"]["total_cost_usd"], 0.003)

        second = models[SECOND_MODEL["model_id"]]
        self.assertIn("429", second["results"][0]["error"])
        self.assertEqual(second["summary"]["successful_tests"], 2)
        self.assertEqual(second["summary"]["failed_tests"], 1)

        # The hand-off file is cleaned up after saving
        self.assertFalse((self.data_dir / runner.RAW_RESULTS_FILE).exists())

    def test_stale_raw_results_are_not_saved(self):
        # Left over from an earlier attempt with other candidate models
        self.write_json(runner.RAW_RESULTS_FILE, {
            "project_name": "Previous attempt",
            "models": [],
        })

        with self.assertRaises(FileNotFoundError):
            self.run_node(
                scripted_runner_agent(
                    "load_runner_inputs",
                    "save_runner_results",
                )
            )

        self.assertFalse((self.data_dir / "runner_results.json").exists())

    def test_invalid_raw_results_are_rejected(self):
        self.write_json(runner.RAW_RESULTS_FILE, {"project_name": "Test project"})

        with self.assertRaises(Exception) as error:
            runner.save_runner_results.invoke({})

        self.assertIn("models", str(error.exception))
        self.assertFalse((self.data_dir / "runner_results.json").exists())


if __name__ == "__main__":
    unittest.main()
