"""Tests for Prompt builder, .static() alias, and inject_context()."""

from adk_fluent import Agent, Prompt

# ======================================================================
# Prompt builder — section methods
# ======================================================================


class TestPromptSections:
    def test_role_only(self):
        p = Prompt().role("You are a helpful assistant.")
        assert str(p) == "You are a helpful assistant."

    def test_task_only(self):
        p = Prompt().task("Summarize the document.")
        assert str(p) == "Task:\nSummarize the document."

    def test_role_and_task(self):
        p = Prompt().role("You are an analyst.").task("Analyze the data.")
        result = str(p)
        assert "You are an analyst." in result
        assert "Task:\nAnalyze the data." in result
        # Role comes before task
        assert result.index("analyst") < result.index("Task")

    def test_all_standard_sections(self):
        p = (
            Prompt()
            .role("You are a reviewer.")
            .context("The code is in Python.")
            .task("Review for bugs.")
            .constraint("Max 5 bullet points.")
            .format("Use markdown.")
            .example("Input: eval(x) | Output: dangerous")
        )
        result = str(p)
        assert "You are a reviewer." in result
        assert "Context:\nThe code is in Python." in result
        assert "Task:\nReview for bugs." in result
        assert "Constraints:\nMax 5 bullet points." in result
        assert "Output Format:\nUse markdown." in result
        assert "Examples:\nInput: eval(x) | Output: dangerous" in result

    def test_section_order_is_fixed(self):
        # Even if called out of order, sections appear in standard order
        p = Prompt().example("example first").role("role second").task("task third")
        result = str(p)
        role_pos = result.index("role second")
        task_pos = result.index("task third")
        example_pos = result.index("example first")
        assert role_pos < task_pos < example_pos

    def test_multiple_constraints(self):
        p = Prompt().constraint("Be concise.").constraint("No jargon.").constraint("Use examples.")
        result = str(p)
        assert "Constraints:\nBe concise.\nNo jargon.\nUse examples." in result

    def test_multiple_examples(self):
        p = Prompt().example("Q: 2+2 A: 4").example("Q: 3+3 A: 6")
        result = str(p)
        assert "Examples:\nQ: 2+2 A: 4\nQ: 3+3 A: 6" in result

    def test_custom_section(self):
        p = Prompt().section("persona", "Act like a pirate.")
        result = str(p)
        assert "Persona:\nAct like a pirate." in result

    def test_custom_sections_after_standard(self):
        p = Prompt().role("Helper.").section("style", "Be formal.")
        result = str(p)
        assert result.index("Helper") < result.index("Style")


# ======================================================================
# Prompt builder — composition
# ======================================================================


class TestPromptComposition:
    def test_merge_combines_sections(self):
        base = Prompt().role("You are helpful.").constraint("Be concise.")
        extra = Prompt().constraint("No jargon.").example("Q: x A: y")
        merged = base.merge(extra)
        result = str(merged)
        assert "Be concise." in result
        assert "No jargon." in result
        assert "Q: x A: y" in result

    def test_merge_is_immutable(self):
        a = Prompt().role("Role A.")
        b = Prompt().task("Task B.")
        merged = a.merge(b)
        # Original prompts unchanged
        assert "Task" not in str(a)
        assert "Role" not in str(b)
        # Merged has both
        assert "Role A." in str(merged)
        assert "Task B." in str(merged)

    def test_add_operator(self):
        a = Prompt().role("Helper.")
        b = Prompt().task("Summarize.")
        result = str(a + b)
        assert "Helper." in result
        assert "Summarize." in result

    def test_reuse_base_prompt(self):
        base = Prompt().role("You are a senior engineer.").constraint("Be precise.")
        reviewer = base + Prompt().task("Review code.")
        writer = base + Prompt().task("Write documentation.")
        assert "Review code." in str(reviewer)
        assert "Write documentation." in str(writer)
        assert "Review" not in str(writer)
        assert "documentation" not in str(reviewer)


# ======================================================================
# Prompt builder — output
# ======================================================================


class TestPromptOutput:
    def test_build_returns_string(self):
        p = Prompt().role("Test.")
        assert isinstance(p.build(), str)

    def test_str_equals_build(self):
        p = Prompt().role("Test.").task("Do things.")
        assert str(p) == p.build()

    def test_repr(self):
        p = Prompt().role("R").task("T").example("E")
        r = repr(p)
        assert "Prompt" in r
        assert "role" in r
        assert "task" in r
        assert "example" in r

    def test_empty_prompt(self):
        p = Prompt()
        assert str(p) == ""

    def test_template_variables_pass_through(self):
        p = Prompt().role("You help with {topic}.").task("Explain {concept} in {topic}.")
        result = str(p)
        assert "{topic}" in result
        assert "{concept}" in result


# ======================================================================
# Prompt + Agent integration
# ======================================================================


class TestPromptWithAgent:
    def test_instruct_accepts_prompt(self):
        prompt = Prompt().role("Helper.").task("Answer questions.")
        agent = Agent("test").model("gemini-2.5-flash").instruct(prompt).build()
        # instruction should be the compiled string
        assert "Helper." in agent.instruction
        assert "Answer questions." in agent.instruction

    def test_static_accepts_prompt(self):
        prompt = Prompt().context("Large reference material here.")
        agent = Agent("test").model("gemini-2.5-flash").static(prompt).instruct("Answer.").build()
        assert "reference material" in str(agent.static_instruction)


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
        # guardrail adds to both before_model and after_model
        # inject_context adds to before_model
        assert len(builder._callbacks["before_model_callback"]) == 2
        assert len(builder._callbacks["after_model_callback"]) == 1
