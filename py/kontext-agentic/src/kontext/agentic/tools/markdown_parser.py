"""Markdown parsing for notebook blocks.

This module converts markdown text into Kontext notebook blocks. It is kept
separate from :mod:`kontext.agentic.tools.notebook_tool` so that the block-building
logic (which is pure and testable in isolation) does not drag the toolkit's
service/editor wiring along with it.

The mistune AST is walked directly (rather than using a mistune renderer) so
that each markdown construct maps to the richest available ``NotebookBlock``
variant (headers keep their level, lists keep ordering/checklist state, tables
keep headings, etc.).
"""

from typing import Any
from uuid import uuid4

import mistune

from kontext.schema import (
    CodeBlock,
    CodeBlockData,
    DelimiterBlock,
    DelimiterBlockData,
    HeaderBlock,
    HeaderBlockData,
    ListBlock,
    ListBlockData,
    ListBlockMeta,
    ListItem,
    ListItemMeta,
    ListStyle,
    NotebookBlock,
    ParagraphBlock,
    ParagraphBlockData,
    QuoteAlignment,
    QuoteBlock,
    QuoteBlockData,
    TableBlock,
    TableBlockData,
)

_SUPPORTED_HEADING_RANGE = (2, 5)


def markdown_to_html(text: str) -> str:
    """Convert a single line/paragraph of markdown to HTML."""
    if not text:
        return ""
    parser = mistune.create_markdown(renderer=None)
    ast = parser(text)
    if not ast:
        return text
    # Usually we want the content of the first paragraph
    for node in ast:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "paragraph":
            return render_inline_html(node.get("children", []))

    first_node = ast[0]
    if isinstance(first_node, dict) and first_node.get("children"):
        return render_inline_html(first_node.get("children", []))
    return text


def render_inline_html(children: list[dict[str, Any]]) -> str:
    """Render mistune inline AST nodes to HTML for EditorJS compatibility."""
    html = ""
    for child in children:
        if not isinstance(child, dict):
            continue
        type_ = child.get("type")
        if type_ == "text":
            html += child.get("raw", "")
        elif type_ == "strong":
            html += f"<b>{render_inline_html(child.get('children', []))}</b>"
        elif type_ == "emphasis":
            html += f"<i>{render_inline_html(child.get('children', []))}</i>"
        elif type_ == "codespan":
            html += f"<code>{child.get('raw', '')}</code>"
        elif type_ == "link":
            href = child.get("attrs", {}).get("url", "")
            title = child.get("attrs", {}).get("title", "")
            text = render_inline_html(child.get("children", []))
            title_attr = f' title="{title}"' if title else ""
            html += f'<a href="{href}"{title_attr} target="_blank">{text}</a>'
        elif type_ == "image":
            src = child.get("attrs", {}).get("url", "")
            alt = child.get("attrs", {}).get("alt", "")
            html += f'<img src="{src}" alt="{alt}">'
        elif type_ == "softbreak":
            html += " "
        elif type_ == "linebreak":
            html += "<br>"
    return html


def normalize_markdown_heading_level(level: Any) -> int:
    """Normalize markdown headings to the supported notebook header range."""
    try:
        parsed_level = int(level)
    except (TypeError, ValueError):
        return _SUPPORTED_HEADING_RANGE[0]
    return min(max(parsed_level, _SUPPORTED_HEADING_RANGE[0]), _SUPPORTED_HEADING_RANGE[1])


def validate_header_level(level: int) -> int:
    """Validate explicit notebook header levels."""
    if level < _SUPPORTED_HEADING_RANGE[0] or level > _SUPPORTED_HEADING_RANGE[1]:
        raise ValueError(
            f"Header level must be between {_SUPPORTED_HEADING_RANGE[0]} and "
            f"{_SUPPORTED_HEADING_RANGE[1]}."
        )
    return level


def parse_markdown(text: str) -> list[NotebookBlock]:
    """Parse markdown text into a list of NotebookBlocks."""
    if not text or not text.strip():
        return []

    parser = mistune.create_markdown(renderer=None, plugins=["table", "task_lists"])
    ast = parser(text)
    blocks = []

    for node in ast:
        if not isinstance(node, dict):
            continue

        type_ = node.get("type")
        if type_ == "heading":
            level = normalize_markdown_heading_level(node.get("attrs", {}).get("level", 2))
            text_content = render_inline_html(node.get("children", []))
            blocks.append(
                NotebookBlock(
                    HeaderBlock(
                        id=str(uuid4()),
                        type="header",
                        data=HeaderBlockData(text=text_content, level=level),
                    )
                )
            )
        elif type_ == "paragraph":
            text_content = render_inline_html(node.get("children", []))
            blocks.append(
                NotebookBlock(
                    ParagraphBlock(
                        id=str(uuid4()),
                        type="paragraph",
                        data=ParagraphBlockData(text=text_content),
                    )
                )
            )
        elif type_ == "list":
            attrs = node.get("attrs", {})
            is_ordered = attrs.get("ordered", False) if isinstance(attrs, dict) else False
            style = ListStyle.ORDERED if is_ordered else ListStyle.UNORDERED
            items = []
            for list_item in node.get("children", []):
                if not isinstance(list_item, dict):
                    continue
                item_content = ""
                li_attrs = list_item.get("attrs", {})
                checked = li_attrs.get("checked") if isinstance(li_attrs, dict) else None
                if checked is not None:
                    style = ListStyle.CHECKLIST

                for child in list_item.get("children", []):
                    if not isinstance(child, dict):
                        continue
                    if child.get("type") == "block_text":
                        if item_content:
                            item_content += "<br>"
                        item_content += render_inline_html(child.get("children", []))

                items.append(
                    ListItem(
                        content=item_content,
                        meta=ListItemMeta(checked=checked),
                        items=[],  # Nested lists omitted for simplicity
                    )
                )

            blocks.append(
                NotebookBlock(
                    ListBlock(
                        id=str(uuid4()),
                        type="list",
                        data=ListBlockData(style=style, items=items, meta=ListBlockMeta()),
                    )
                )
            )
        elif type_ == "block_code":
            code = node.get("raw", "").strip()
            blocks.append(
                NotebookBlock(
                    CodeBlock(id=str(uuid4()), type="code", data=CodeBlockData(code=code))
                )
            )

        elif type_ == "block_quote":
            text_content = ""
            for child in node.get("children", []):
                if not isinstance(child, dict):
                    continue
                if child.get("type") == "paragraph":
                    if text_content:
                        text_content += "<br>"
                    text_content += render_inline_html(child.get("children", []))
            blocks.append(
                NotebookBlock(
                    QuoteBlock(
                        id=str(uuid4()),
                        type="quote",
                        data=QuoteBlockData(
                            text=text_content, caption="", alignment=QuoteAlignment.LEFT
                        ),
                    )
                )
            )
        elif type_ == "table":
            content = []
            with_headings = False
            for section in node.get("children", []):
                if not isinstance(section, dict):
                    continue
                if section.get("type") == "table_head":
                    with_headings = True
                    # table_head children are table_cells directly (mistune 3.x)
                    r = []
                    for cell in section.get("children", []):
                        if isinstance(cell, dict):
                            r.append(render_inline_html(cell.get("children", [])))
                    if r:
                        content.append(r)
                elif section.get("type") == "table_body":
                    for row in section.get("children", []):
                        if not isinstance(row, dict):
                            continue
                        r = []
                        for cell in row.get("children", []):
                            if isinstance(cell, dict):
                                r.append(render_inline_html(cell.get("children", [])))
                        content.append(r)
            blocks.append(
                NotebookBlock(
                    TableBlock(
                        id=str(uuid4()),
                        type="table",
                        data=TableBlockData(with_headings=with_headings, content=content),
                    )
                )
            )
        elif type_ == "thematic_break":
            blocks.append(
                NotebookBlock(
                    DelimiterBlock(id=str(uuid4()), type="delimiter", data=DelimiterBlockData())
                )
            )
    return blocks
