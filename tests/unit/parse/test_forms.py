"""Form extraction tests."""

from webscraper.parse.forms import extract_forms


def test_extract_forms_captures_fields_with_labels() -> None:
    html = """
    <form action="/submit" method="POST">
      <label for="q">Search</label>
      <input type="text" id="q" name="q" />
      <textarea name="notes"></textarea>
      <input type="checkbox" name="agree" />
    </form>
    """
    forms = extract_forms(html)
    assert len(forms) == 1
    f = forms[0]
    assert f.action == "/submit"
    assert f.method == "POST"
    names = [x.name for x in f.fields]
    assert names == ["q", "notes", "agree"]
    types = {x.name: x.type for x in f.fields}
    assert types == {"q": "text", "notes": "textarea", "agree": "checkbox"}
    labels = {x.name: x.label for x in f.fields}
    assert labels["q"] == "Search"


def test_extract_forms_defaults_method_to_get() -> None:
    html = "<form><input name='x' /></form>"
    assert extract_forms(html)[0].method == "GET"


def test_extract_forms_empty_when_no_forms() -> None:
    assert extract_forms("<p>no forms</p>") == []
