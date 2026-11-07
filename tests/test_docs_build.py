"""Тесты сборки программной документации (``docs/build_docx.py``).

Проверяется, что преобразователь Markdown → DOCX разбирает заголовки, таблицы,
блоки кода и выделение текста, а также что настоящие разделы документации
собираются в один файл без ошибок.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

pytest.importorskip("docx")

from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = PROJECT_ROOT / "docs" / "build_docx.py"

DOC_SOURCES = (
    "intro.md",
    "theory.md",
    "program.md",
    "mapping.md",
    "repo.md",
    "user_guide.md",
    "api.md",
)

SAMPLE_MARKDOWN = """# Раздел

Абзац с **жирным**, `кодом` и *курсивом*.

| Ключ | Значение |
| --- | --- |
| a | 1 |
| b | 2 |

- пункт один
- пункт два

```text
A + B = [3, 8]
```

1. первый
2. второй

> примечание
"""


@pytest.fixture(scope="module")
def builder() -> ModuleType:
    """Загрузить скрипт сборки как модуль."""
    spec = importlib.util.spec_from_file_location("docs_build_docx", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def sample_markdown(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")
    return path


def test_build_from_sample(builder: ModuleType, sample_markdown: Path, tmp_path: Path) -> None:
    output = builder.build_document([sample_markdown], tmp_path / "sample.docx")
    assert output.exists()

    document = Document(str(output))
    styles = [paragraph.style.name for paragraph in document.paragraphs]

    assert "Heading 1" in styles
    assert "Код" in styles
    assert "Цитата" in styles
    assert [paragraph.text for paragraph in document.paragraphs if paragraph.style.name == "Heading 1"] == [
        "Раздел",
    ]
    assert "TOC Heading" in styles

    # Содержание — настоящее поле Word; при открытии Word обновит его сам.
    field_codes = [
        node.text or ""
        for node in document.element.body.findall(f".//{qn('w:instrText')}")
    ]
    assert any(code.startswith("TOC") for code in field_codes)
    assert document.settings.element.find(qn("w:updateFields")) is not None

    # Первая таблица — таблица из Markdown с жирной шапкой.
    table = document.tables[0]
    assert [cell.text for cell in table.rows[0].cells] == ["Ключ", "Значение"]
    assert [cell.text for cell in table.rows[1].cells] == ["a", "1"]
    assert all(run.bold for run in table.rows[0].cells[0].paragraphs[0].runs)

    # Строка кода выводится как есть, моноширинным стилем.
    code = next(p for p in document.paragraphs if p.style.name == "Код")
    assert code.text == 'A + B = [3, 8]'
    assert document.styles["Код"].font.name == "Consolas"


def test_markdown_is_not_left_in_text(builder: ModuleType, sample_markdown: Path, tmp_path: Path) -> None:
    output = builder.build_document([sample_markdown], tmp_path / "sample.docx")
    document = Document(str(output))

    for paragraph in document.paragraphs:
        if paragraph.style.name == "Код":
            continue
        assert "**" not in paragraph.text
        assert "```" not in paragraph.text
        assert not paragraph.text.strip().startswith("|")

    bullet = next(p for p in document.paragraphs if p.text.startswith("• пункт один"))
    assert bullet.runs[1].bold is None
    bold = next(p for p in document.paragraphs if p.text.startswith("Абзац с"))
    assert any(run.bold for run in bold.runs)


def test_document_fonts_are_explicit(builder: ModuleType) -> None:
    document = builder.setup_document()

    for style_name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Title", "TOC Heading"):
        style = document.styles[style_name]
        xml = style.element.xml
        # Ссылки на шрифт темы заставляют Word показывать Calibri.
        assert "asciiTheme" not in xml
        assert "hAnsiTheme" not in xml
        assert "Times New Roman" in xml

    # Связанные стили символов тоже не должны ссылаться на тему.
    for style in document.styles:
        if style.name == "Код" or style.type == builder.WD_STYLE_TYPE.TABLE:
            continue
        assert "asciiTheme" not in style.element.xml
        assert "hAnsiTheme" not in style.element.xml

    theme = next(
        part
        for part in document.part.package.parts
        if str(part.partname) == "/word/theme/theme1.xml"
    )
    assert b"Calibri" not in theme.blob

    assert document.styles["Normal"].font.size.pt == 14.0
    for style_name in ("Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        assert document.styles[style_name].font.size.pt == 16.0

    code = document.styles["Код"]
    assert code.font.name == "Consolas"
    assert code.font.size.pt == 14.0


def test_real_documentation_builds(builder: ModuleType, tmp_path: Path) -> None:
    sources = [PROJECT_ROOT / "docs" / name for name in DOC_SOURCES]
    for source in sources:
        assert source.exists(), f"нет файла документации: {source}"

    output = builder.build_document(sources, tmp_path / "documentation.docx")
    document = Document(str(output))

    top_level = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
    assert top_level == [
        "Задание",
        "Теоретический раздел",
        "Описание программы",
        "Место математических формул в программе",
        "Где лежит проект и как собрать",
        "Руководство пользователя",
        "Описание программного интерфейса (API)",
    ]
    assert len(document.tables) >= 35

    # Содержание — поле TOC Word, а не обычный список заголовков.
    field_codes = [
        node.text or ""
        for node in document.element.body.findall(f".//{qn('w:instrText')}")
    ]
    assert any(code.startswith("TOC") for code in field_codes)

    # Ключевые сведения пояснительной записки присутствуют в тексте.
    text = "\n".join(p.text for p in document.paragraphs)
    assert "https://github.com/DmitriyKolesnikM8O/Non-Classical-logics.git" in text
    assert "Где лежит проект и как собрать" in text
    assert "docs\\build_docx.py" in text


def test_title_page_is_inserted(builder: ModuleType, sample_markdown: Path, tmp_path: Path) -> None:
    title_page = PROJECT_ROOT / "docs" / "Титульник.docx"
    if not title_page.exists():
        pytest.skip("нет файла docs/Титульник.docx")

    output = builder.build_document(
        [sample_markdown], tmp_path / "titled.docx", title_page=title_page
    )
    document = Document(str(output))

    texts = [paragraph.text for paragraph in document.paragraphs]
    assert "Московский авиационный институт" in texts
    assert "Москва — 2026" in texts

    # Автоматический заголовок не добавляется: титул занимает первую страницу.
    assert not any(paragraph.style.name == "Title" for paragraph in document.paragraphs)
    assert document.sections[0].different_first_page_header_footer is True

    # Разрыв страницы задан свойством page_break_before у «Содержания»,
    # а не отдельным пустым абзацем — иначе появляется лишняя пустая страница.
    toc_heading = next(p for p in document.paragraphs if p.text == "Содержание")
    assert toc_heading.paragraph_format.page_break_before is True
    assert not any(
        br.get(qn("w:type")) == "page"
        for br in document.element.body.findall(f".//{qn('w:br')}")
    )


def test_text_toc_skips_python_comments(builder: ModuleType, tmp_path: Path) -> None:
    source = tmp_path / "comments.md"
    source.write_text(
        "# Раздел\n\n"
        "```python\n"
        "# это комментарий, а не заголовок\n"
        "value = 1\n"
        "```\n",
        encoding="utf-8",
    )
    output = builder.build_document([source], tmp_path / "comments.docx", toc="text")
    document = Document(str(output))

    toc_entries = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.style.name == "Normal"
        and paragraph.text in {"Раздел", "# это комментарий, а не заголовок"}
    ]
    assert toc_entries == ["Раздел"]

    code_lines = [p.text for p in document.paragraphs if p.style.name == "Код"]
    assert "# это комментарий, а не заголовок" in code_lines
    assert "value = 1" in code_lines

