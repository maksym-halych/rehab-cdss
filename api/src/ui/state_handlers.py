import os
import gradio as gr


def _sanitize_pushup_overrides(files, overrides):
    ov = dict(overrides or {})
    valid: set[str] = set()
    for f in files or []:
        p = str(getattr(f, "name", str(f)))
        base = os.path.basename(p).lower()
        if base.endswith(".csv") and "pushup_analysis" in base:
            valid.add(p)
    for k in list(ov.keys()):
        if str(k) not in valid:
            ov.pop(k, None)
    return ov


def _sanitize_manual_test_overrides(files, overrides):
    ov = dict(overrides or {})
    valid = {str(getattr(f, "name", str(f))) for f in (files or [])}
    for k in list(ov.keys()):
        if str(k) not in valid:
            ov.pop(k, None)
    return ov


def remove_file_from_states(
    current_files,
    pushup_overrides,
    manual_overrides,
    refresh_token,
    target_path: str,
):
    files = list(current_files or [])
    tgt = str(target_path)
    kept = []
    for f in files:
        p = str(getattr(f, "name", str(f)))
        if p == tgt:
            continue
        kept.append(f)

    pushup_overrides = dict(pushup_overrides or {})
    manual_overrides = dict(manual_overrides or {})
    pushup_overrides.pop(tgt, None)
    manual_overrides.pop(tgt, None)

    pushup_overrides = _sanitize_pushup_overrides(kept, pushup_overrides)
    manual_overrides = _sanitize_manual_test_overrides(kept, manual_overrides)

    try:
        refresh_next = int(refresh_token) + 1
    except Exception:
        refresh_next = 1

    return (
        kept,
        pushup_overrides,
        manual_overrides,
        refresh_next,
        gr.update(value="", visible=False),
        gr.update(value=None, visible=False, variant="secondary"),
    )


def add_files_to_list(
    newly_uploaded_files,
    current_file_list,
    pushup_overrides,
    manual_overrides,
    refresh_token,
):
    if current_file_list is None:
        current_file_list = []
    if newly_uploaded_files:
        if isinstance(newly_uploaded_files, list):
            current_file_list.extend(newly_uploaded_files)
        else:
            current_file_list.append(newly_uploaded_files)

    pushup_overrides = _sanitize_pushup_overrides(current_file_list, pushup_overrides)
    manual_overrides = _sanitize_manual_test_overrides(
        current_file_list, manual_overrides
    )
    try:
        refresh_next = int(refresh_token) + 1
    except Exception:
        refresh_next = 1
    return (
        current_file_list,
        pushup_overrides,
        manual_overrides,
        refresh_next,
        gr.update(value="", visible=False),
        gr.update(value=None, visible=False, variant="secondary"),
    )


def clear_all_files(refresh_token):
    try:
        refresh_next = int(refresh_token) + 1
    except Exception:
        refresh_next = 1
    return (
        [],
        {},
        {},
        refresh_next,
        gr.update(value="", visible=False),
        gr.update(value=None, visible=False, variant="secondary"),
    )
