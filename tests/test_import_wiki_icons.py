import importlib.util
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "import_wiki_icons.py"


def _tool():
    spec = importlib.util.spec_from_file_location("import_wiki_icons", _TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_STENCIL_ROW = (
    '<tr><td>5 </td><td><span typeof="mw:File"><a href="/wiki/File:Icon_Stencil_X.png"><img src="/w/images/thumb/x.webp"/></a>'
    '<a href="/w/images/1/13/Icon_Stencil_Milky_Terraccota.png" class="mw-file-source"></a></span></td>'
    "<td>Milky Terraccota</td><td>Canto Hairpin</td></tr>"
)
_FURNITURE_ROW = (
    '<tr><td><figure><a href="/w/images/8/84/Study_Piano_Design.png" class="mw-file-source"></a></figure></td>'
    "<td>Study Piano Design</td><td>5x Planks</td></tr>"
)


def test_parse_skips_index_cells_and_finds_the_full_size_file():
    pairs = _tool().parse_table_rows("<table>" + _STENCIL_ROW + _FURNITURE_ROW + "<tr><td>no image</td></tr></table>")
    assert pairs == [
        ("Milky Terraccota", "/w/images/1/13/Icon_Stencil_Milky_Terraccota.png"),
        ("Study Piano Design", "/w/images/8/84/Study_Piano_Design.png"),
    ]


def test_match_is_exact_fuzzy_or_none():
    tool = _tool()
    available = {
        tool.norm("Milky Terraccota"): ("Milky Terraccota", "/p/a.png"),
        tool.norm("Study Piano Design"): ("Study Piano Design", "/p/b.png"),
        tool.norm("Verdigris"): ("Verdigris", "/p/c.png"),
    }
    # the game's name has no trailing 'Design'; the wiki's does -> still an EXACT match
    assert tool.match_icon("Study Piano", available) == ("Study Piano Design", "/p/b.png", "exact")
    assert tool.match_icon("verdigris", available)[2] == "exact"
    # a wiki typo is caught, but flagged FUZZY so a human reviews it
    assert tool.match_icon("Milky Terracotta", available) == ("Milky Terraccota", "/p/a.png", "fuzzy")
    assert tool.match_icon("Totally Different", available) is None


def test_norm_does_not_eat_names_that_merely_end_in_design():
    assert _tool().norm("Design") == "design"
