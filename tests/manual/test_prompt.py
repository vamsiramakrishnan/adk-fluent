"""Tests for P module — frozen dataclass prompt composition.

Tests mirror the structure of test_context.py: protocol, sections, composition,
conditional, template, structural transforms, LLM transforms, integration, IR.
"""

from adk_fluent import (
    Agent,
    P,
    PAdapt,
    PComposite,
    PCompress,
    PConstraint,
    PContext,
    PExample,
    PFormat,
    PFromState,
    POnly,
    PPipe,
    PReorder,
    PRole,
    PScaffolded,
    PSection,
    PTask,
    PTemplate,
    PTransform,
    PVersioned,
    PWhen,
    PWithout,
)

# ======================================================================
# Protocol: Frozen immutability and type hierarchy
# ======================================================================


class TestProtocol:
    def test_ptransform_is_frozen(self):
        t = PTransform()
        try:
            t._kind = "changed"
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass

    def test_prole_is_frozen(self):
        r = PRole(content="test")
        try:
            r.content = "changed"
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass

    def test_all_types_are_ptransform(self):
        types = [
            PRole(content="r"),
            PContext(content="c"),
            PTask(content="t"),
            PConstraint(content="c"),
            PFormat(content="f"),
            PExample(content="e"),
            PSection(name="s", content="s"),
            PComposite(blocks=()),
            PPipe(),
            PWhen(),
            PFromState(),
            PTemplate(),
            PReorder(),
            POnly(),
            PWithout(),
            PCompress(),
            PAdapt(),
            PScaffolded(),
            PVersioned(),
        ]
        for t in types:
            assert isinstance(t, PTransform), f"{type(t).__name__} is not PTransform"

    def test_kind_discriminator(self):
        assert PRole(content="x")._kind == "role"
        assert PContext(content="x")._kind == "context"
        assert PTask(content="x")._kind == "task"
        assert PConstraint(content="x")._kind == "constraint"
        assert PFormat(content="x")._kind == "format"
        assert PExample(content="x")._kind == "example"
        assert PSection(name="s", content="x")._kind == "section"
        assert PComposite()._kind == "composite"
        assert PPipe()._kind == "pipe"
        assert PWhen()._kind == "when"
        assert PFromState()._kind == "from_state"
        assert PTemplate()._kind == "template"


# ======================================================================
# Phase A: Core section output
# ======================================================================


class TestCoreSections:
    def test_role_no_header(self):
        result = str(P.role("You are a helpful assistant."))
        assert result == "You are a helpful assistant."

    def test_task_with_header(self):
        result = str(P.task("Summarize the document."))
        assert result == "Task:\nSummarize the document."

    def test_context_with_header(self):
        result = str(P.context("Python 3.11 codebase."))
        assert result == "Context:\nPython 3.11 codebase."

    def test_constraint_with_header(self):
        result = str(P.constraint("Be concise."))
        assert result == "Constraints:\nBe concise."

    def test_format_with_header(self):
        result = str(P.format("Return JSON."))
        assert result == "Output Format:\nReturn JSON."

    def test_example_freeform(self):
        result = str(P.example("Q: 2+2 A: 4"))
        assert result == "Examples:\nQ: 2+2 A: 4"

    def test_example_structured(self):
        result = str(P.example(input="eval(x)", output="Critical"))
        assert "Input: eval(x)" in result
        assert "Output: Critical" in result

    def test_custom_section(self):
        result = str(P.section("persona", "Act like a pirate."))
        assert "Persona:\nAct like a pirate." in result

    def test_multiple_constraints(self):
        result = str(P.constraint("Be concise.", "No jargon.", "Use examples."))
        assert "Constraints:" in result
        assert "Be concise." in result
        assert "No jargon." in result
        assert "Use examples." in result

    def test_empty_build(self):
        result = str(PTransform())
        assert result == ""


# ======================================================================
# Composition: + operator (PComposite)
# ======================================================================


class TestComposition:
    def test_add_creates_composite(self):
        result = P.role("R") + P.task("T")
        assert isinstance(result, PComposite)
        assert len(result.blocks) == 2

    def test_composite_flattens(self):
        a = P.role("R")
        b = P.task("T")
        c = P.constraint("C")
        result = (a + b) + c
        assert isinstance(result, PComposite)
        assert len(result.blocks) == 3

    def test_composite_preserves_all_sections(self):
        result = P.role("Reviewer.") + P.task("Review code.") + P.constraint("Be concise.")
        text = str(result)
        assert "Reviewer." in text
        assert "Task:\nReview code." in text
        assert "Constraints:\nBe concise." in text

    def test_section_order_is_fixed(self):
        result = P.example("example first") + P.role("role second") + P.task("task third")
        text = str(result)
        role_pos = text.index("role second")
        task_pos = text.index("task third")
        example_pos = text.index("example first")
        assert role_pos < task_pos < example_pos

    def test_same_kind_merges(self):
        result = P.constraint("Rule 1.") + P.constraint("Rule 2.") + P.constraint("Rule 3.")
        text = str(result)
        assert "Constraints:\nRule 1.\nRule 2.\nRule 3." in text

    def test_multiple_examples_merge(self):
        result = P.example("Q: 2+2 A: 4") + P.example("Q: 3+3 A: 6")
        text = str(result)
        assert "Examples:\nQ: 2+2 A: 4\nQ: 3+3 A: 6" in text

    def test_reuse_base_prompt(self):
        base = P.role("You are a senior engineer.") + P.constraint("Be precise.")
        reviewer = base + P.task("Review code.")
        writer = base + P.task("Write documentation.")
        assert "Review code." in str(reviewer)
        assert "Write documentation." in str(writer)
        assert "Review" not in str(writer)
        assert "documentation" not in str(reviewer)

    def test_custom_sections_after_standard(self):
        result = P.role("Helper.") + P.section("style", "Be formal.")
        text = str(result)
        assert text.index("Helper") < text.index("Style")


# ======================================================================
# Composition: | operator (PPipe)
# ======================================================================


class TestPipe:
    def test_pipe_creates_ppipe(self):
        result = P.role("R") | P.compress(max_tokens=100)
        assert isinstance(result, PPipe)
        assert isinstance(result.source, PRole)
        assert isinstance(result.transform, PCompress)

    def test_pipe_static_passthrough(self):
        source = P.role("Reviewer.") + P.task("Review.")
        result = source | P.compress(max_tokens=100)
        text = str(result)
        assert "Reviewer." in text
        assert "Review." in text


# ======================================================================
# Phase B: Conditional & Dynamic
# ======================================================================


class TestConditional:
    def test_when_with_true_callable(self):
        result = P.role("Helper") + P.when(lambda s: True, P.context("Extra info."))
        text = result.build(state={"anything": True})
        assert "Extra info." in text

    def test_when_with_false_callable(self):
        result = P.role("Helper") + P.when(lambda s: False, P.context("Hidden."))
        text = result.build()
        assert "Hidden." not in text

    def test_when_with_state_key_string(self):
        result = P.role("Helper") + P.when("verbose", P.context("Detailed info."))
        text = result.build(state={"verbose": True})
        assert "Detailed info." in text
        text = result.build(state={"verbose": False})
        assert "Detailed info." not in text
        text = result.build(state={})
        assert "Detailed info." not in text

    def test_when_exception_in_predicate(self):
        result = P.role("Helper") + P.when(lambda s: 1 / 0, P.context("Error."))
        text = result.build()
        assert "Error." not in text


class TestFromState:
    def test_from_state_renders_keys(self):
        result = P.role("Helper") + P.from_state("name", "plan")
        text = result.build(state={"name": "Alice", "plan": "pro"})
        assert "name: Alice" in text
        assert "plan: pro" in text

    def test_from_state_missing_keys(self):
        result = P.from_state("name", "missing_key")
        text = result.build(state={"name": "Alice"})
        assert "name: Alice" in text
        assert "missing_key" not in text


class TestTemplate:
    def test_template_basic(self):
        result = P.template("Help with {topic} in {style} tone.")
        text = result.build(state={"topic": "Python", "style": "casual"})
        assert "Help with Python in casual tone." in text

    def test_template_optional_vars(self):
        result = P.template("Help with {topic}. Note: {extra?}")
        text = result.build(state={"topic": "Python"})
        assert "Help with Python." in text

    def test_template_passthrough(self):
        result = P.template("Help with {topic}.")
        text = result.build(state={})
        assert "{topic}" in text

    def test_template_variables_in_role(self):
        result = P.role("You help with {topic}.")
        text = str(result)
        assert "{topic}" in text


# ======================================================================
# Phase C: Structural Transforms
# ======================================================================


class TestStructuralTransforms:
    def test_only_keeps_named(self):
        from adk_fluent._prompt import _apply_structural_transform

        groups = {"role": ["R"], "task": ["T"], "constraint": ["C"], "format": ["F"]}
        filtered = _apply_structural_transform(POnly(names=("role", "task")), groups)
        assert "role" in filtered
        assert "task" in filtered
        assert "constraint" not in filtered
        assert "format" not in filtered

    def test_without_removes_named(self):
        from adk_fluent._prompt import _apply_structural_transform

        groups = {"role": ["R"], "task": ["T"], "constraint": ["C"]}
        filtered = _apply_structural_transform(PWithout(names=("constraint",)), groups)
        assert "role" in filtered
        assert "task" in filtered
        assert "constraint" not in filtered


# ======================================================================
# Phase E: Sugar
# ======================================================================


class TestSugar:
    def test_scaffolded(self):
        inner = P.role("Helper") + P.task("Do stuff.")
        result = P.scaffolded(inner, preamble="SAFETY FIRST", postamble="STAY SAFE")
        text = str(result)
        assert "SAFETY FIRST" in text
        assert "Do stuff." in text
        assert "STAY SAFE" in text

    def test_versioned_builds_inner(self):
        inner = P.role("Helper") + P.task("Do stuff.")
        result = P.versioned(inner, tag="v1.0")
        text = str(result)
        assert "Helper" in text
        assert "Do stuff." in text


# ======================================================================
# Fingerprinting
# ======================================================================


class TestFingerprint:
    def test_deterministic(self):
        a = P.role("Hello")
        assert a.fingerprint() == a.fingerprint()

    def test_different_content_different_hash(self):
        a = P.role("Hello")
        b = P.role("World")
        assert a.fingerprint() != b.fingerprint()

    def test_composite_fingerprint(self):
        a = P.role("R") + P.task("T")
        b = P.role("R") + P.task("T")
        assert a.fingerprint() == b.fingerprint()

    def test_different_composite_fingerprint(self):
        a = P.role("R") + P.task("T1")
        b = P.role("R") + P.task("T2")
        assert a.fingerprint() != b.fingerprint()

    def test_versioned_fingerprint(self):
        inner = P.role("Helper")
        v = P.versioned(inner, tag="v1")
        assert len(v.fingerprint()) == 12


# ======================================================================
# P namespace factories
# ======================================================================


class TestPNamespace:
    def test_role_returns_prole(self):
        assert isinstance(P.role("x"), PRole)

    def test_context_returns_pcontext(self):
        assert isinstance(P.context("x"), PContext)

    def test_task_returns_ptask(self):
        assert isinstance(P.task("x"), PTask)

    def test_constraint_single_returns_pconstraint(self):
        assert isinstance(P.constraint("x"), PConstraint)

    def test_constraint_multiple_returns_composite(self):
        result = P.constraint("a", "b", "c")
        assert isinstance(result, PComposite)
        assert len(result.blocks) == 3

    def test_format_returns_pformat(self):
        assert isinstance(P.format("x"), PFormat)

    def test_example_freeform_returns_pexample(self):
        assert isinstance(P.example("x"), PExample)

    def test_example_structured_returns_pexample(self):
        result = P.example(input="i", output="o")
        assert isinstance(result, PExample)
        assert result.input_text == "i"
        assert result.output_text == "o"

    def test_section_returns_psection(self):
        result = P.section("name", "text")
        assert isinstance(result, PSection)
        assert result.name == "name"

    def test_when_returns_pwhen(self):
        assert isinstance(P.when("key", P.task("x")), PWhen)

    def test_from_state_returns_pfromstate(self):
        result = P.from_state("a", "b")
        assert isinstance(result, PFromState)
        assert result.keys == ("a", "b")

    def test_template_returns_ptemplate(self):
        assert isinstance(P.template("hello {x}"), PTemplate)

    def test_compress_returns_pcompress(self):
        result = P.compress(max_tokens=100)
        assert isinstance(result, PCompress)
        assert result.max_tokens == 100

    def test_adapt_returns_padapt(self):
        result = P.adapt(audience="executive")
        assert isinstance(result, PAdapt)
        assert result.audience == "executive"

    def test_scaffolded_returns_pscaffolded(self):
        result = P.scaffolded(P.task("x"))
        assert isinstance(result, PScaffolded)

    def test_versioned_returns_pversioned(self):
        result = P.versioned(P.task("x"), tag="v1")
        assert isinstance(result, PVersioned)
        assert result.tag == "v1"


# ======================================================================
# repr
# ======================================================================


class TestRepr:
    def test_prole_repr(self):
        assert "PRole" in repr(P.role("hello"))

    def test_pcomposite_repr(self):
        result = P.role("R") + P.task("T")
        r = repr(result)
        assert "PComposite" in r
        assert "role" in r
        assert "task" in r

    def test_ppipe_repr(self):
        result = P.role("R") | P.compress()
        r = repr(result)
        assert "PPipe" in r


# ======================================================================
# Agent integration
# ======================================================================


class TestAgentIntegration:
    def test_instruct_accepts_ptransform(self):
        prompt = P.role("Helper.") + P.task("Answer questions.")
        agent = Agent("test").model("gemini-2.5-flash").instruct(prompt).build()
        assert "Helper." in agent.instruction
        assert "Answer questions." in agent.instruction

    def test_static_accepts_ptransform(self):
        prompt = P.context("Large reference material here.")
        agent = Agent("test").model("gemini-2.5-flash").static(prompt).instruct("Answer.").build()
        assert "reference material" in str(agent.static_instruction)

    def test_instruct_accepts_string(self):
        agent = Agent("test").model("gemini-2.5-flash").instruct("Plain string.").build()
        assert agent.instruction == "Plain string."


# ======================================================================
# IR integration
# ======================================================================


class TestIRIntegration:
    def test_prompt_spec_preserved_in_ir(self):
        prompt = P.role("Reviewer") + P.task("Review code.")
        ir = Agent("r").model("gemini-2.5-flash").instruct(prompt).to_ir()
        assert ir.prompt_spec is not None
        assert isinstance(ir.prompt_spec, PComposite)

    def test_prompt_spec_none_by_default(self):
        ir = Agent("r").model("gemini-2.5-flash").instruct("plain").to_ir()
        assert ir.prompt_spec is None

    def test_prompt_spec_single_section(self):
        ir = Agent("r").model("gemini-2.5-flash").instruct(P.role("Test")).to_ir()
        assert ir.prompt_spec is not None
        assert isinstance(ir.prompt_spec, PRole)


# ======================================================================
# Dynamic compilation
# ======================================================================


class TestDynamicCompilation:
    def test_static_prompt_returns_string(self):
        from adk_fluent._prompt import _compile_prompt_spec

        prompt = P.role("Helper") + P.task("Do stuff.")
        result = _compile_prompt_spec(prompt)
        assert isinstance(result, str)
        assert "Helper" in result

    def test_dynamic_prompt_returns_callable(self):
        from adk_fluent._prompt import _compile_prompt_spec

        prompt = P.role("Helper") + P.when("verbose", P.context("Extra."))
        result = _compile_prompt_spec(prompt)
        assert callable(result)

    def test_from_state_returns_callable(self):
        from adk_fluent._prompt import _compile_prompt_spec

        prompt = P.role("Helper") + P.from_state("name")
        result = _compile_prompt_spec(prompt)
        assert callable(result)

    def test_template_returns_callable(self):
        from adk_fluent._prompt import _compile_prompt_spec

        prompt = P.template("Hello {name}")
        result = _compile_prompt_spec(prompt)
        assert callable(result)


# ======================================================================
# Template variable extraction
# ======================================================================


class TestTemplateVars:
    def test_extract_required(self):
        from adk_fluent._prompt import _extract_template_vars

        required, optional = _extract_template_vars("Hello {name}, welcome to {place}.")
        assert "name" in required
        assert "place" in required
        assert len(optional) == 0

    def test_extract_optional(self):
        from adk_fluent._prompt import _extract_template_vars

        required, optional = _extract_template_vars("Hello {name}. Note: {extra?}")
        assert "name" in required
        assert "extra" in optional

    def test_extract_namespaced(self):
        from adk_fluent._prompt import _extract_template_vars

        required, optional = _extract_template_vars("Setting: {app:theme}")
        assert "app:theme" in required

    def test_resolve_template(self):
        from adk_fluent._prompt import _resolve_template

        result = _resolve_template("Hello {name}!", {"name": "Alice"})
        assert result == "Hello Alice!"

    def test_resolve_optional_missing(self):
        from adk_fluent._prompt import _resolve_template

        result = _resolve_template("Hello{extra?}!", {})
        assert result == "Hello!"

    def test_resolve_passthrough(self):
        from adk_fluent._prompt import _resolve_template

        result = _resolve_template("Hello {name}!", {})
        assert result == "Hello {name}!"


# ======================================================================
# .static() alias
# ======================================================================


class TestStaticAlias:
    def test_static_sets_static_instruction(self):
        agent = Agent("test").model("gemini-2.5-flash").static("Cached context.").instruct("Dynamic.").build()
        assert agent.static_instruction == "Cached context."
        assert agent.instruction == "Dynamic."

    def test_static_in_aliases(self):
        assert "static" in Agent._ALIASES
        assert Agent._ALIASES["static"] == "static_instruction"

    def test_static_chains(self):
        builder = Agent("test").static("Context.").instruct("Task.")
        assert builder._config["static_instruction"] == "Context."
        assert builder._config["instruction"] == "Task."


# ======================================================================
# inject_context()
# ======================================================================


class TestInjectContext:
    def test_inject_context_adds_before_model_callback(self):
        builder = Agent("test").model("gemini-2.5-flash").inject_context(lambda ctx: "extra context")
        assert len(builder._callbacks["before_model_callback"]) == 1

    def test_inject_context_chains(self):
        builder = (
            Agent("test")
            .model("gemini-2.5-flash")
            .inject_context(lambda ctx: "first")
            .inject_context(lambda ctx: "second")
        )
        assert len(builder._callbacks["before_model_callback"]) == 2

    def test_inject_context_with_instruct(self):
        builder = (
            Agent("test")
            .model("gemini-2.5-flash")
            .instruct("Main instruction.")
            .inject_context(lambda ctx: "Dynamic context.")
        )
        agent = builder.build()
        assert agent.instruction == "Main instruction."
        assert len(builder._callbacks["before_model_callback"]) == 1

    def test_inject_context_composes_with_guardrail(self):
        def my_guardrail(ctx, req):
            pass

        builder = Agent("test").model("gemini-2.5-flash").guardrail(my_guardrail).inject_context(lambda ctx: "extra")
        assert len(builder._callbacks["before_model_callback"]) == 2
        assert len(builder._callbacks["after_model_callback"]) == 1
