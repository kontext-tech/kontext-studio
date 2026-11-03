from pydantic import BaseModel

from kontext.agentic.utils.tool_result_utils import tool_result_to_str


class _BrokenToolResult(BaseModel):
    value: int = 1

    def to_dict(self):
        raise RuntimeError("broken to_dict")

    def model_dump_json(self, *args, **kwargs):
        raise RuntimeError("broken model_dump_json")

    def model_dump(self, *args, **kwargs):
        raise RuntimeError("broken model_dump")

    def __str__(self) -> str:
        return "broken-tool-result"


def test_tool_result_to_str_falls_back_to_string_when_serializers_fail() -> None:
    assert tool_result_to_str(_BrokenToolResult()) == "broken-tool-result"
