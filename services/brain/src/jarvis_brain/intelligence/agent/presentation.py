"""English product presentation from typed results; paths stay outside model feedback."""


def file_page(data, scope=None):
    entries = data["entries"]
    start = data.get("offset", 0) + 1
    lines = (
        [f"{data['total']} results; showing {start}–{start + len(entries) - 1}."]
        if entries
        else ["No results on this page."]
    )
    for number, entry in enumerate(entries, 1):
        kind = "folder" if entry["kind"] == "directory" else "file"
        line = f"{number}. {entry['name']} ({kind}) — {entry['location']}"
        if entry["kind"] == "file" and "size_bytes" in entry:
            line += f" — {entry['size_bytes']} bytes"
        lines.append(line)
    if data.get("partial"):
        lines.append("Partial catalog: files outside the scanned scope may be missing.")
    if scope:
        lines.append(f"Search folder: {scope['name']}.")
    if entries:
        lines.append("Choose a name or number, or ask to open an item's containing folder.")
    if data.get("offset", 0) + len(entries) < data["total"]:
        lines.append("Say 'next page' for more results.")
    return "\n".join(lines)


def operation_failure(code):
    return {
        "application_not_found": "The requested application was not found in the catalog.",
        "application_ambiguous": "Several applications matched; choose one by name.",
        "application_selection_stale": "The application selection changed; choose it again.",
        "unknown_tool": "The running Core lacks this operation; restart the updated Core.",
        "policy_denied": "Core policy denied this operation.",
        "permission_denied": "Access to this operation was denied.",
        "execution_failed": (
            "The operation could not be completed. Check access or storage availability."
        ),
        "invalid_arguments": (
            "The parameters or selected item are no longer valid; "
            "check the request or list the items again."
        ),
        "confirmation_required": "Core policy requires confirmation before this operation.",
    }.get(code, "The operation could not be completed. Check the request and current selection.")
