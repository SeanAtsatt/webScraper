"""Extract <form> elements into FormSpec."""

from selectolax.parser import HTMLParser, Node

from webscraper.envelope import FormField, FormSpec

_FIELD_TAGS = {"input", "textarea", "select"}


def _labels_by_for(tree: HTMLParser) -> dict[str, str]:
    out: dict[str, str] = {}
    for lbl in tree.css("label[for]"):
        target = lbl.attributes.get("for") or ""
        if target:
            out[target] = lbl.text(strip=True)
    return out


def _walk(node: Node) -> list[Node]:
    """Return all descendant nodes in document (depth-first) order."""
    result: list[Node] = []
    child = node.child
    while child is not None:
        result.append(child)
        result.extend(_walk(child))
        child = child.next
    return result


def extract_forms(html: str) -> list[FormSpec]:
    tree = HTMLParser(html)
    label_map = _labels_by_for(tree)
    out: list[FormSpec] = []
    for form in tree.css("form"):
        fields: list[FormField] = []
        for node in _walk(form):
            tag = (node.tag or "").lower()
            if tag not in _FIELD_TAGS:
                continue
            name = node.attributes.get("name") or ""
            if not name:
                continue
            input_type = (
                "textarea"
                if tag == "textarea"
                else "select"
                if tag == "select"
                else (node.attributes.get("type") or "text").lower()
            )
            field_id = node.attributes.get("id") or ""
            label = label_map.get(field_id, "")
            fields.append(FormField(name=name, type=input_type, label=label))
        action = form.attributes.get("action") or ""
        method = (form.attributes.get("method") or "GET").upper()
        out.append(FormSpec(action=action, method=method, fields=fields))
    return out
