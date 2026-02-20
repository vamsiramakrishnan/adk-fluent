"""Tests for the seed generator."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Classification ---
def test_classify_agent():
    from scripts.seed_generator import classify_class

    assert classify_class("LlmAgent", "google.adk.agents.llm_agent", ["LlmAgent", "BaseAgent", "BaseModel"]) == "agent"
    assert (
        classify_class("SequentialAgent", "google.adk.agents.sequential_agent", ["SequentialAgent", "BaseAgent"])
        == "agent"
    )
    assert classify_class("BaseAgent", "google.adk.agents.base_agent", ["BaseAgent", "BaseModel"]) == "agent"


def test_classify_service():
    from scripts.seed_generator import classify_class

    assert (
        classify_class(
            "InMemorySessionService", "google.adk.sessions.in_memory_session_service", ["InMemorySessionService"]
        )
        == "service"
    )


def test_classify_config():
    from scripts.seed_generator import classify_class

    assert classify_class("RunConfig", "google.adk.agents.run_config", ["RunConfig", "BaseModel"]) == "config"


def test_classify_tool():
    from scripts.seed_generator import classify_class

    assert classify_class("FunctionTool", "google.adk.tools.function_tool", ["FunctionTool", "BaseTool"]) == "tool"


def test_classify_runtime():
    from scripts.seed_generator import classify_class

    assert classify_class("App", "google.adk.apps.app", ["App", "BaseModel"]) == "runtime"
    assert classify_class("Runner", "google.adk.runners", ["Runner"]) == "runtime"


def test_classify_plugin():
    from scripts.seed_generator import classify_class

    assert classify_class("LoggingPlugin", "google.adk.plugins.logging_plugin", ["LoggingPlugin"]) == "plugin"


def test_classify_planner():
    from scripts.seed_generator import classify_class

    assert (
        classify_class("PlanReActPlanner", "google.adk.planners.plan_re_act_planner", ["PlanReActPlanner"]) == "planner"
    )


def test_classify_executor():
    from scripts.seed_generator import classify_class

    assert (
        classify_class(
            "BuiltInCodeExecutor", "google.adk.code_executors.built_in_code_executor", ["BuiltInCodeExecutor"]
        )
        == "executor"
    )


def test_classify_eval():
    from scripts.seed_generator import classify_class

    assert classify_class("EvalCase", "google.adk.evaluation.eval_case", ["EvalCase", "BaseModel"]) == "eval"


def test_classify_auth():
    from scripts.seed_generator import classify_class

    assert classify_class("AuthCredential", "google.adk.auth.auth_credential", ["AuthCredential"]) == "auth"


def test_classify_data():
    from scripts.seed_generator import classify_class

    assert classify_class("Session", "google.adk.sessions.session", ["Session", "BaseModel"]) == "data"


def test_is_builder_worthy():
    from scripts.seed_generator import is_builder_worthy

    assert is_builder_worthy("agent") is True
    assert is_builder_worthy("config") is True
    assert is_builder_worthy("runtime") is True
    assert is_builder_worthy("eval") is False
    assert is_builder_worthy("data") is False


# --- Field Policies ---
def test_field_policy_skip():
    from scripts.seed_generator import get_field_policy

    assert get_field_policy("parent_agent", "Optional[BaseAgent]", False) == "skip"
    assert get_field_policy("_private", "str", False) == "skip"


def test_field_policy_additive():
    from scripts.seed_generator import get_field_policy

    assert get_field_policy("before_model_callback", "Union[Callable, None]", True) == "additive"


def test_field_policy_list_extend():
    from scripts.seed_generator import get_field_policy

    assert get_field_policy("tools", "list[BaseTool]", False) == "list_extend"
    assert get_field_policy("sub_agents", "list[BaseAgent]", False) == "list_extend"


def test_field_policy_normal():
    from scripts.seed_generator import get_field_policy

    assert get_field_policy("instruction", "str | Callable", False) == "normal"


# --- Type-Driven Field Policies ---
def test_field_policy_infers_list_extend_from_type():
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("tools", "list[BaseTool]", False) == "list_extend"
    assert infer_field_policy("sub_agents", "list[BaseAgent]", False) == "list_extend"
    assert infer_field_policy("artifacts", "list[Artifact]", False) == "list_extend"
    assert infer_field_policy("examples", "list[Example]", False) == "list_extend"
    # Union-wrapped lists (common in Pydantic Optional fields)
    assert infer_field_policy("sub_agents", "Union[list[AgentRefConfig], NoneType]", False) == "list_extend"
    assert infer_field_policy("tools", "Union[list[ToolConfig], NoneType]", False) == "list_extend"
    # Pipe-union syntax
    assert infer_field_policy("plugins", "list[BasePlugin] | None", False) == "list_extend"


def test_field_policy_infers_additive_from_callback():
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("before_model_callback", "Callable | None", True) == "additive"
    assert infer_field_policy("on_error_callback", "Callable | None", True) == "additive"


def test_field_policy_infers_skip_from_internals():
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("model_config", "ConfigDict", False) == "skip"
    assert infer_field_policy("model_fields", "dict", False) == "skip"
    assert infer_field_policy("_private", "str", False) == "skip"
    assert infer_field_policy("parent_agent", "BaseAgent | None", False, is_parent_ref=True) == "skip"


def test_field_policy_normal_fallback():
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("instruction", "str | None", False) == "normal"
    assert infer_field_policy("temperature", "float", False) == "normal"


def test_field_policy_list_of_primitives_is_normal():
    from scripts.seed_generator import infer_field_policy

    assert infer_field_policy("tags", "list[str]", False) == "normal"
    assert infer_field_policy("names", "list[int]", False) == "normal"


# --- Aliases ---
def test_generate_aliases():
    from scripts.seed_generator import generate_aliases

    aliases = generate_aliases(["instruction", "description", "model", "tools"])
    assert aliases == {"instruct": "instruction", "describe": "description"}


# --- Morphological Alias Derivation ---
def test_derive_alias_strips_tion_suffix():
    from scripts.seed_generator import derive_alias

    assert derive_alias("instruction") == "instruct"
    assert derive_alias("description") == "describe"
    assert derive_alias("configuration") == "configure"
    assert derive_alias("execution") == "execute"


def test_derive_alias_strips_ment_suffix():
    from scripts.seed_generator import derive_alias

    assert derive_alias("deployment") == "deploy"
    assert derive_alias("assignment") == "assign"


def test_derive_alias_returns_none_for_short_names():
    from scripts.seed_generator import derive_alias

    assert derive_alias("model") is None
    assert derive_alias("name") is None
    assert derive_alias("tools") is None


def test_derive_alias_returns_none_for_no_pattern():
    from scripts.seed_generator import derive_alias

    assert derive_alias("temperature") is None
    assert derive_alias("max_tokens") is None


def test_derive_aliases_batch():
    from scripts.seed_generator import derive_aliases

    fields = ["instruction", "description", "model", "tools", "temperature"]
    aliases = derive_aliases(fields)
    assert aliases == {"instruct": "instruction", "describe": "description"}


def test_derive_aliases_with_overrides():
    from scripts.seed_generator import derive_aliases

    fields = ["instruction", "output_key", "include_contents"]
    overrides = {"outputs": "output_key", "history": "include_contents"}
    aliases = derive_aliases(fields, overrides=overrides)
    assert aliases["instruct"] == "instruction"  # Derived
    assert aliases["outputs"] == "output_key"  # Override
    assert aliases["history"] == "include_contents"  # Override


def test_generate_callback_aliases():
    from scripts.seed_generator import generate_callback_aliases

    aliases = generate_callback_aliases(["before_model_callback", "after_agent_callback"])
    assert aliases == {"before_model": "before_model_callback", "after_agent": "after_agent_callback"}


# --- Constructor Args ---
def test_detect_constructor_args_pydantic():
    from scripts.seed_generator import detect_constructor_args

    fields = [
        {"name": "name", "required": True},
        {"name": "model", "required": True},
        {"name": "instruction", "required": False},
    ]
    assert detect_constructor_args(fields, "pydantic", []) == ["name", "model"]


def test_detect_constructor_args_init_signature():
    from scripts.seed_generator import detect_constructor_args

    init_params = [
        {"name": "agent", "required": True},
        {"name": "app_name", "required": True},
        {"name": "svc", "required": False},
    ]
    assert detect_constructor_args([], "init_signature", init_params) == ["agent", "app_name"]


# --- Module Grouping ---
def test_determine_output_module():
    from scripts.seed_generator import determine_output_module

    assert determine_output_module("SequentialAgent", "agent", "google.adk.agents") == "workflow"
    assert determine_output_module("LlmAgent", "agent", "google.adk.agents") == "agent"
    assert determine_output_module("RunConfig", "config", "google.adk.agents") == "config"


# --- Extras ---
def test_generate_extras_sequential():
    from scripts.seed_generator import generate_extras

    extras = generate_extras("SequentialAgent", "agent", "google.adk.agents.SequentialAgent")
    assert any(e["name"] == "step" for e in extras)


def test_generate_extras_llm_agent():
    from scripts.seed_generator import generate_extras

    extras = generate_extras("LlmAgent", "agent", "google.adk.agents.LlmAgent")
    assert any(e["name"] == "tool" for e in extras)
    assert any(e["name"] == "apply" for e in extras)


def test_generate_extras_non_agent():
    from scripts.seed_generator import generate_extras

    assert generate_extras("RunConfig", "config", "x") == []


# --- TOML Emission ---
def test_emit_seed_toml():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    from scripts.seed_generator import emit_seed_toml

    builders = [
        {
            "name": "Agent",
            "source_class": "google.adk.agents.llm_agent.LlmAgent",
            "output_module": "agent",
            "doc": "Fluent builder for LlmAgent.",
            "constructor_args": ["name", "model"],
            "aliases": {"instruct": "instruction"},
            "callback_aliases": {"before_model": "before_model_callback"},
            "extra_skip_fields": [],
            "terminals": [{"name": "build", "returns": "LlmAgent"}],
            "extras": [],
            "tag": "agent",
        }
    ]
    global_config = {
        "skip_fields": ["parent_agent"],
        "additive_fields": ["before_model_callback"],
        "list_extend_fields": ["tools"],
    }
    toml_str = emit_seed_toml(builders, global_config, adk_version="1.25.0")
    parsed = tomllib.loads(toml_str)
    assert "meta" in parsed
    assert "global" in parsed
    assert "Agent" in parsed["builders"]
    assert parsed["builders"]["Agent"]["source_class"] == "google.adk.agents.llm_agent.LlmAgent"


# --- Integration ---
def test_generate_seed_from_manifest_end_to_end():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    from scripts.scanner import manifest_to_dict, scan_all
    from scripts.seed_generator import generate_seed_from_manifest

    manifest = scan_all()
    manifest_dict = manifest_to_dict(manifest)
    toml_str = generate_seed_from_manifest(manifest_dict)
    parsed = tomllib.loads(toml_str)

    assert "meta" in parsed
    assert "global" in parsed
    assert "builders" in parsed
    builder_names = list(parsed["builders"].keys())
    assert len(builder_names) > 7, f"Only {len(builder_names)}: {builder_names}"

    # Must include LlmAgent as "Agent"
    assert "Agent" in parsed["builders"]
    assert "Pipeline" in parsed["builders"]  # SequentialAgent renamed


# --- Type-Driven Extras ---
def test_infer_extras_singular_adder_for_list_field():
    from scripts.seed_generator import infer_extras

    fields = [
        {"name": "tools", "type_str": "list[BaseTool]", "is_callback": False},
        {"name": "sub_agents", "type_str": "list[BaseAgent]", "is_callback": False},
    ]
    extras = infer_extras("SomeAgent", "agent", fields)
    tool_extra = next((e for e in extras if e["name"] == "tool"), None)
    assert tool_extra is not None
    assert tool_extra["behavior"] == "list_append"
    assert tool_extra["target_field"] == "tools"
    sub_agent_extra = next((e for e in extras if e["name"] == "sub_agent"), None)
    assert sub_agent_extra is not None
    assert sub_agent_extra["behavior"] == "list_append"
    assert sub_agent_extra["target_field"] == "sub_agents"


def test_infer_extras_step_for_sub_agents_in_sequential():
    from scripts.seed_generator import infer_extras

    fields = [{"name": "sub_agents", "type_str": "list[BaseAgent]", "is_callback": False}]
    extras = infer_extras("SequentialAgent", "agent", fields)
    step = next((e for e in extras if e["name"] == "step"), None)
    assert step is not None
    assert step["target_field"] == "sub_agents"


def test_infer_extras_branch_for_parallel():
    from scripts.seed_generator import infer_extras

    fields = [{"name": "sub_agents", "type_str": "list[BaseAgent]", "is_callback": False}]
    extras = infer_extras("ParallelAgent", "agent", fields)
    branch = next((e for e in extras if e["name"] == "branch"), None)
    assert branch is not None


def test_infer_extras_no_duplicates_with_manual():
    from scripts.seed_generator import merge_extras

    inferred = [
        {"name": "tool", "behavior": "list_append", "target_field": "tools"},
    ]
    manual = [
        {
            "name": "tool",
            "behavior": "runtime_helper",
            "helper_func": "_add_tool",
            "signature": "(self, fn_or_tool, *, require_confirmation: bool = False) -> Self",
        },
    ]
    merged = merge_extras(inferred, manual)
    assert len([e for e in merged if e["name"] == "tool"]) == 1
    assert merged[0]["behavior"] == "runtime_helper"


def test_infer_extras_unknown_class_gets_generic_adders():
    from scripts.seed_generator import infer_extras

    fields = [
        {"name": "evaluators", "type_str": "list[BaseEvaluator]", "is_callback": False},
    ]
    extras = infer_extras("EvalSuite", "eval", fields)
    evaluator_extra = next((e for e in extras if e["name"] == "evaluator"), None)
    assert evaluator_extra is not None
    assert evaluator_extra["target_field"] == "evaluators"


# --- Parent Reference Detection (A5) ---
def test_detect_parent_ref_from_mro():
    from scripts.seed_generator import is_parent_reference

    mro = ["LlmAgent", "BaseAgent", "BaseModel"]
    assert is_parent_reference("parent_agent", "BaseAgent | None", mro) is True
    assert is_parent_reference("parent_agent", "BaseAgent | None", ["Unrelated"]) is False
    assert is_parent_reference("delegate", "BaseAgent | None", mro) is False  # name doesn't match
    assert is_parent_reference("model", "str", mro) is False
    assert is_parent_reference("owner_agent", "BaseAgent | None", mro) is True
