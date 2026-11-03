import kontext.agentic.blueprints as blueprints
from kontext.agent import AgentKind
from kontext.agentic.blueprints.python_agent import PYTHON_AGENT_DESCRIPTOR


def test_python_agent_blueprint_is_exported() -> None:
    assert "build_python_spec" in blueprints.__all__
    assert callable(blueprints.build_python_spec)
    assert PYTHON_AGENT_DESCRIPTOR.id is AgentKind.PYTHON
