"""Tests for ExecutionConfig compaction wiring to ADK App."""


def test_compaction_wired_to_app():
    """ExecutionConfig.compaction produces App with events_compaction_config."""
    from adk_fluent import Agent, ExecutionConfig, CompactionConfig
    config = ExecutionConfig(
        compaction=CompactionConfig(interval=5, overlap=1)
    )
    a = Agent("a").instruct("hi")
    app = a.to_app(config=config)
    assert app.events_compaction_config is not None


def test_no_compaction_by_default():
    """Without compaction config, App has no events_compaction_config."""
    from adk_fluent import Agent
    a = Agent("a").instruct("hi")
    app = a.to_app()
    assert app.events_compaction_config is None


def test_compaction_interval_maps_correctly():
    """CompactionConfig fields map to ADK EventsCompactionConfig fields."""
    from adk_fluent import Agent, ExecutionConfig, CompactionConfig
    config = ExecutionConfig(
        compaction=CompactionConfig(interval=20, overlap=3)
    )
    app = Agent("a").instruct("hi").to_app(config=config)
    ecc = app.events_compaction_config
    assert ecc.compaction_interval == 20
    assert ecc.overlap_size == 3
