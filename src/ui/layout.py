import os
import gradio as gr

from module_1_aggregation.config import CHECK_PERSON_IDENTITY
from module_1_aggregation.processing.file_detection import detect_files
from module_1_aggregation.processing.person_detection import (
    UNKNOWN_PERSON_KEY,
    build_people_index,
)
from module_1_aggregation.processing.pipeline import process_files
from .state_handlers import (
    add_files_to_list,
    clear_all_files,
    remove_file_from_states,
)
from .styles import APP_CSS


def _build_variant_families() -> dict[str, dict]:
    return {
        "push_up_family": {
            "choices": [
                ("Push Up", "push_up"),
                ("Handstand Push Up", "handstand_push_up"),
            ],
            "default": "push_up",
        }
    }


def _build_pushup_candidates(detected: dict) -> list[str]:
    return [str(p) for p in (detected.get("csv_push_up_paths") or []) if p is not None]


def _build_pdf_groups(files_by_type: dict) -> list[tuple[str, list[str]]]:
    pdf_label_map: dict[str, str] = {
        "dental": "Dental (PDF)",
        "postural": "Postural (PDF)",
        "baropodometry": "Static baropodometry (PDF)",
        "dynamic_baropodometry": "Dynamic baropodometry (PDF)",
        "spine3d": "Spine 3D (PDF)",
    }
    pdf_groups: list[tuple[str, list[str]]] = []
    if isinstance(files_by_type, dict):
        for key in [
            "postural",
            "spine3d",
            "baropodometry",
            "dynamic_baropodometry",
            "dental",
        ]:
            items = files_by_type.get(key) or []
            if not items:
                continue
            paths = [str(getattr(f, "name", str(f))) for f in items]
            pdf_groups.append((pdf_label_map.get(key, f"{key} (PDF)"), paths))
    return pdf_groups


def _build_csv_groups(detected: dict, pushup_candidates: list[str]) -> list[dict]:
    return [
        {
            "label": "Cervical goniometry (CSV)",
            "paths": detected.get("csv_goniometry_paths") or [],
        },
        {
            "label": "Leg goniometry (CSV)",
            "paths": detected.get("csv_leg_goniometry_paths") or [],
        },
        {
            "label": "Leg dynamometry (CSV)",
            "paths": detected.get("csv_leg_dynamometry_paths") or [],
        },
        {
            "label": "Arm goniometry (CSV)",
            "paths": detected.get("csv_arm_goniometry_paths") or [],
        },
        {
            "label": "Arm dynamometry (CSV)",
            "paths": detected.get("csv_arm_dynamometry_paths") or [],
        },
        {
            "label": "Single leg balance (CSV)",
            "paths": detected.get("csv_single_leg_balance_paths") or [],
        },
        {
            "label": "Single leg landing (CSV)",
            "paths": detected.get("csv_single_leg_landing_paths") or [],
        },
        {
            "label": "McCall hamstrings (CSV)",
            "paths": detected.get("csv_mccall_paths") or [],
        },
        {
            "label": "Shoulder test (CSV)",
            "paths": detected.get("csv_shoulder_paths") or [],
        },
        {
            "label": "Push Up (CSV)",
            "paths": pushup_candidates,
            "variant_family": "push_up_family",
        },
        {
            "label": "Counter Movement Jump (CSV)",
            "paths": detected.get("csv_counter_movement_jump_paths") or [],
        },
        {
            "label": "Single Leg Counter Movement Jump (CSV)",
            "paths": detected.get("csv_single_leg_counter_movement_jump_paths") or [],
        },
        {
            "label": "Drop Jump (CSV)",
            "paths": detected.get("csv_drop_jump_paths") or [],
        },
        {"label": "IMTP (CSV)", "paths": detected.get("csv_imtp_paths") or []},
        {
            "label": "Bipodal stance (CSV)",
            "paths": detected.get("csv_bipodal_stance_paths") or [],
        },
        {
            "label": "Bipodal landing (CSV)",
            "paths": detected.get("csv_bipodal_landing_paths") or [],
        },
        {"label": "Skipping (CSV)", "paths": detected.get("csv_skipping_paths") or []},
        {
            "label": "Squats advanced analysis (CSV)",
            "paths": detected.get("csv_squats_advanced_analysis_paths") or [],
        },
    ]


def _collect_recognized(
    pdf_groups: list[tuple[str, list[str]]], csv_groups: list[dict]
) -> set[str]:
    recognized: set[str] = set()
    for _, paths in pdf_groups:
        for p in paths:
            recognized.add(str(p))
    for g in csv_groups:
        for p in g.get("paths") or []:
            recognized.add(str(p))
    return recognized


def _build_groups(
    csv_groups: list[dict],
    pdf_groups: list[tuple[str, list[str]]],
    unknown_paths: list[str],
) -> list[dict]:
    variant_groups: list[dict] = []
    other_groups: list[dict] = []

    for g in csv_groups:
        paths = g.get("paths") or []
        if not paths:
            continue
        item = {
            "label": g.get("label", ""),
            "paths": [str(p) for p in paths],
            "variant_family": g.get("variant_family"),
        }
        if g.get("variant_family"):
            variant_groups.append(item)
        else:
            other_groups.append(item)

    other_groups = other_groups + [
        {"label": label, "paths": paths} for label, paths in pdf_groups if paths
    ]

    groups: list[dict] = []
    groups.extend(variant_groups)
    groups.extend(other_groups)
    if unknown_paths:
        groups.append(
            {"label": "Невідомі / не розпізнані файли", "paths": unknown_paths}
        )
    return groups


def _lock_ui():
    disabled = gr.update(interactive=False)
    return (
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
    )


def _unlock_ui():
    enabled = gr.update(interactive=True)
    return (
        enabled,
        enabled,
        enabled,
        enabled,
        enabled,
        enabled,
        enabled,
        enabled,
        enabled,
    )


def _bump_refresh(refresh_token):
    try:
        return int(refresh_token) + 1
    except Exception:
        return 1


def _set_manual_person_name(value, refresh_token):
    return str(value or ""), _bump_refresh(refresh_token)


def _reset_person_name(refresh_token):
    return "", "", "", _bump_refresh(refresh_token)


def _reset_person_name_if_ok(warning_html, current_name, current_code, refresh_token):
    if warning_html:
        value = str(current_name or "")
        code_value = str(current_code or "")
        return value, value, code_value, refresh_token
    return "", "", "", _bump_refresh(refresh_token)


def build_app():
    with gr.Blocks(theme=gr.themes.Soft(), css=APP_CSS) as demo:
        file_list_state = gr.State([])
        pushup_type_overrides_state = gr.State({})
        manual_test_overrides_state = gr.State({})
        selected_person_key_state = gr.State("")
        manual_person_name_state = gr.State("")
        ui_refresh_token = gr.Number(value=0, visible=False)

        with gr.Row():
            with gr.Column(scale=3, min_width=520):
                gr.Markdown("### Файли")

                @gr.render(
                    inputs=[
                        ui_refresh_token,
                        file_list_state,
                        pushup_type_overrides_state,
                        manual_test_overrides_state,
                        selected_person_key_state,
                        manual_person_name_state,
                    ]
                )
                def _render_uploaded_files(
                    _tick,
                    files,
                    pushup_overrides,
                    manual_overrides,
                    selected_person_key,
                    manual_person_name,
                ):
                    files = files or []
                    pushup_overrides = (
                        pushup_overrides if isinstance(pushup_overrides, dict) else {}
                    )
                    manual_overrides = (
                        manual_overrides if isinstance(manual_overrides, dict) else {}
                    )

                    if not files:
                        return

                    if not CHECK_PERSON_IDENTITY:
                        gr.Markdown(
                            "Перевірку особи вимкнено. Аналізуються всі завантажені файли."
                        )

                    all_paths = [str(getattr(f, "name", str(f))) for f in files]
                    people, path_to_guess = build_people_index(
                        all_paths, manual_name=manual_person_name
                    )
                    selectable_people = [
                        p for p in people if p.key != UNKNOWN_PERSON_KEY
                    ]
                    selectable_keys = [p.key for p in selectable_people]

                    current_sel = str(selected_person_key or "").strip()
                    default_sel = (
                        current_sel if current_sel in set(selectable_keys) else ""
                    )
                    manual_name_clean = str(manual_person_name or "").strip()
                    if manual_name_clean:
                        for p in selectable_people:
                            if str(p.display or "").strip() == manual_name_clean:
                                default_sel = p.key
                                break
                    if not default_sel and len(selectable_keys) == 1:
                        default_sel = selectable_keys[0]

                    if selectable_people:
                        gr.Markdown("#### Особа для аналізу")
                        radio = gr.Radio(
                            choices=[(p.display, p.key) for p in selectable_people],
                            value=default_sel or None,
                            show_label=False,
                            interactive=True,
                        )

                        def _set_person(choice, refresh_token):
                            key = str(choice or "")
                            display = ""
                            if key:
                                for p in selectable_people:
                                    if p.key == key:
                                        display = str(p.display or "")
                                        break
                            return key, display, display, _bump_refresh(refresh_token)

                        radio.change(
                            fn=_set_person,
                            inputs=[radio, ui_refresh_token],
                            outputs=[
                                selected_person_key_state,
                                person_name_input,
                                manual_person_name_state,
                                ui_refresh_token,
                            ],
                            queue=False,
                        )
                        if len(selectable_keys) > 1 and not default_sel:
                            gr.Markdown("**Увага:** виявлено файли різних осіб. ")
                    else:
                        if CHECK_PERSON_IDENTITY:
                            gr.Markdown(
                                "**Увага:** не вдалося визначити особу з назв файлів. "
                                "Такі файли буде показано в блоці 'Не розпізнано' і вони не підуть в аналіз."
                            )
                        else:
                            gr.Markdown(
                                "**Увага:** не вдалося визначити особу з назв файлів. "
                                "Такі файли буде показано в блоці 'Не розпізнано' і вони не підуть в аналіз."
                            )

                    detected = detect_files(files)
                    files_by_type = (
                        detected.get("files_by_type", {})
                        if isinstance(detected, dict)
                        else {}
                    )

                    variant_families = _build_variant_families()
                    pushup_candidates = _build_pushup_candidates(detected)
                    pdf_groups = _build_pdf_groups(files_by_type)
                    csv_groups = _build_csv_groups(detected, pushup_candidates)
                    recognized = _collect_recognized(pdf_groups, csv_groups)
                    unknown_paths: list[str] = []
                    for f in files:
                        p = str(getattr(f, "name", str(f)))
                        if p not in recognized:
                            unknown_paths.append(p)

                    groups = _build_groups(csv_groups, pdf_groups, unknown_paths)

                    for person in people:
                        person_paths = {
                            p
                            for p in all_paths
                            if path_to_guess.get(p)
                            and path_to_guess[p].key == person.key
                        }
                        if not person_paths:
                            continue
                        title = f"Особа: {person.display} ({len(person_paths)})"
                        with gr.Accordion(
                            title, open=bool(default_sel and person.key == default_sel)
                        ):
                            groups_for_person: list[dict] = []
                            for g in groups:
                                label0 = str(g.get("label", ""))
                                paths0 = g.get("paths") or []
                                if not isinstance(paths0, list) or not paths0:
                                    continue
                                filtered = [
                                    str(p) for p in paths0 if str(p) in person_paths
                                ]
                                if filtered:
                                    item = dict(g)
                                    item["label"] = label0
                                    item["paths"] = filtered
                                    groups_for_person.append(item)

                            for g in groups_for_person:
                                label = str(g.get("label", ""))
                                paths = g.get("paths") or []
                                if not isinstance(paths, list) or not paths:
                                    continue
                                family_id = g.get("variant_family")
                                family = (
                                    variant_families.get(str(family_id))
                                    if family_id is not None
                                    else None
                                )
                                with gr.Accordion(
                                    f"{label} ({len(paths)})", open=False
                                ):
                                    for p in paths:
                                        base = os.path.basename(str(p))
                                        if family:
                                            default_variant = str(
                                                family.get("default") or "push_up"
                                            )
                                            value = str(
                                                pushup_overrides.get(str(p))
                                                or default_variant
                                            )
                                            with gr.Row(key=f"file-row::{p}"):
                                                with gr.Column(scale=6):
                                                    gr.Markdown(f"`{base}`")
                                                with gr.Column(scale=2, min_width=180):
                                                    dd = gr.Dropdown(
                                                        choices=family.get("choices")
                                                        or [],
                                                        value=value,
                                                        show_label=False,
                                                        interactive=True,
                                                        key=f"variant::{family_id}::{p}",
                                                    )
                                                with gr.Column(scale=1, min_width=44):
                                                    rm = gr.Button(
                                                        "×",
                                                        size="sm",
                                                        variant="secondary",
                                                        key=f"rm::{p}",
                                                    )

                                            def _set_variant(
                                                choice,
                                                current_overrides,
                                                path=str(p),
                                                default=default_variant,
                                            ):
                                                new = dict(current_overrides or {})
                                                c = (
                                                    str(choice)
                                                    if choice is not None
                                                    else ""
                                                )
                                                if c and c != str(default):
                                                    new[path] = c
                                                else:
                                                    new.pop(path, None)
                                                return new

                                            dd.change(
                                                fn=_set_variant,
                                                inputs=[
                                                    dd,
                                                    pushup_type_overrides_state,
                                                ],
                                                outputs=pushup_type_overrides_state,
                                                queue=False,
                                            )

                                            def _remove_this(
                                                cur_files,
                                                cur_push,
                                                cur_manual,
                                                cur_tick,
                                                target=str(p),
                                            ):
                                                return remove_file_from_states(
                                                    cur_files,
                                                    cur_push,
                                                    cur_manual,
                                                    cur_tick,
                                                    target,
                                                )

                                            rm.click(
                                                fn=_remove_this,
                                                inputs=[
                                                    file_list_state,
                                                    pushup_type_overrides_state,
                                                    manual_test_overrides_state,
                                                    ui_refresh_token,
                                                ],
                                                outputs=[
                                                    file_list_state,
                                                    pushup_type_overrides_state,
                                                    manual_test_overrides_state,
                                                    ui_refresh_token,
                                                    warning_display,
                                                    download_button,
                                                ],
                                                queue=False,
                                            )
                                        else:
                                            if (
                                                label
                                                == "Невідомі / не розпізнані файли"
                                            ):
                                                with gr.Row(key=f"file-row::{p}"):
                                                    with gr.Column(scale=6):
                                                        gr.Markdown(f"`{base}`")
                                                    with gr.Column(
                                                        scale=3, min_width=220
                                                    ):
                                                        ext = os.path.splitext(
                                                            base.lower()
                                                        )[1]
                                                        if ext == ".pdf":
                                                            choices = [
                                                                (
                                                                    "Dental (PDF)",
                                                                    "dental",
                                                                ),
                                                                (
                                                                    "Postural (PDF)",
                                                                    "postural",
                                                                ),
                                                                (
                                                                    "Static baropodometry (PDF)",
                                                                    "baropodometry",
                                                                ),
                                                                (
                                                                    "Dynamic baropodometry (PDF)",
                                                                    "dynamic_baropodometry",
                                                                ),
                                                                (
                                                                    "Spine 3D (PDF)",
                                                                    "spine3d",
                                                                ),
                                                            ]
                                                        else:
                                                            choices = [
                                                                (
                                                                    "Cervical goniometry (CSV)",
                                                                    "cervical_goniometry",
                                                                ),
                                                                (
                                                                    "Leg goniometry (CSV)",
                                                                    "leg_goniometry",
                                                                ),
                                                                (
                                                                    "Leg dynamometry (CSV)",
                                                                    "leg_dynamometry",
                                                                ),
                                                                (
                                                                    "Arm goniometry (CSV)",
                                                                    "arm_goniometry",
                                                                ),
                                                                (
                                                                    "Arm dynamometry (CSV)",
                                                                    "arm_dynamometry",
                                                                ),
                                                                (
                                                                    "Single leg balance (CSV)",
                                                                    "single_leg_balance",
                                                                ),
                                                                (
                                                                    "Single leg landing (CSV)",
                                                                    "single_leg_landing",
                                                                ),
                                                                (
                                                                    "McCall hamstrings (CSV)",
                                                                    "mccall_hamstrings",
                                                                ),
                                                                (
                                                                    "Shoulder test (CSV)",
                                                                    "shoulder_test",
                                                                ),
                                                                (
                                                                    "Push Up (CSV)",
                                                                    "push_up",
                                                                ),
                                                                (
                                                                    "Handstand Push Up (CSV)",
                                                                    "handstand_push_up",
                                                                ),
                                                                (
                                                                    "Counter Movement Jump (CSV)",
                                                                    "counter_movement_jump",
                                                                ),
                                                                (
                                                                    "Single Leg Counter Movement Jump (CSV)",
                                                                    "single_leg_counter_movement_jump",
                                                                ),
                                                                (
                                                                    "Drop Jump (CSV)",
                                                                    "drop_jump",
                                                                ),
                                                                ("IMTP (CSV)", "imtp"),
                                                                (
                                                                    "Bipodal stance (CSV)",
                                                                    "bipodal_stance",
                                                                ),
                                                                (
                                                                    "Bipodal landing (CSV)",
                                                                    "bipodal_landing",
                                                                ),
                                                                (
                                                                    "Skipping (CSV)",
                                                                    "skipping",
                                                                ),
                                                                (
                                                                    "Squats advanced analysis (CSV)",
                                                                    "squats_advanced_analysis",
                                                                ),
                                                            ]
                                                        dd_unknown = gr.Dropdown(
                                                            choices=choices,
                                                            value=manual_overrides.get(
                                                                str(p)
                                                            ),
                                                            show_label=False,
                                                            interactive=True,
                                                            key=f"manual-test::{p}",
                                                        )
                                                    with gr.Column(
                                                        scale=1, min_width=44
                                                    ):
                                                        rm_u = gr.Button(
                                                            "×",
                                                            size="sm",
                                                            variant="secondary",
                                                            key=f"rm::{p}",
                                                        )

                                                def _set_manual_test(
                                                    choice,
                                                    current_overrides,
                                                    path=str(p),
                                                ):
                                                    new = dict(current_overrides or {})
                                                    if choice:
                                                        new[path] = str(choice)
                                                    return new

                                                dd_unknown.change(
                                                    fn=_set_manual_test,
                                                    inputs=[
                                                        dd_unknown,
                                                        manual_test_overrides_state,
                                                    ],
                                                    outputs=manual_test_overrides_state,
                                                    queue=False,
                                                )

                                                def _remove_unknown(
                                                    cur_files,
                                                    cur_push,
                                                    cur_manual,
                                                    cur_tick,
                                                    target=str(p),
                                                ):
                                                    return remove_file_from_states(
                                                        cur_files,
                                                        cur_push,
                                                        cur_manual,
                                                        cur_tick,
                                                        target,
                                                    )

                                                rm_u.click(
                                                    fn=_remove_unknown,
                                                    inputs=[
                                                        file_list_state,
                                                        pushup_type_overrides_state,
                                                        manual_test_overrides_state,
                                                        ui_refresh_token,
                                                    ],
                                                    outputs=[
                                                        file_list_state,
                                                        pushup_type_overrides_state,
                                                        manual_test_overrides_state,
                                                        ui_refresh_token,
                                                        warning_display,
                                                        download_button,
                                                    ],
                                                    queue=False,
                                                )
                                            else:
                                                with gr.Row(key=f"file-row::{p}"):
                                                    with gr.Column(scale=8):
                                                        gr.Markdown(f"`{base}`")
                                                    with gr.Column(
                                                        scale=1, min_width=44
                                                    ):
                                                        rm_o = gr.Button(
                                                            "×",
                                                            size="sm",
                                                            variant="secondary",
                                                            key=f"rm::{p}",
                                                        )

                                                def _remove_other(
                                                    cur_files,
                                                    cur_push,
                                                    cur_manual,
                                                    cur_tick,
                                                    target=str(p),
                                                ):
                                                    return remove_file_from_states(
                                                        cur_files,
                                                        cur_push,
                                                        cur_manual,
                                                        cur_tick,
                                                        target,
                                                    )

                                                rm_o.click(
                                                    fn=_remove_other,
                                                    inputs=[
                                                        file_list_state,
                                                        pushup_type_overrides_state,
                                                        manual_test_overrides_state,
                                                        ui_refresh_token,
                                                    ],
                                                    outputs=[
                                                        file_list_state,
                                                        pushup_type_overrides_state,
                                                        manual_test_overrides_state,
                                                        ui_refresh_token,
                                                        warning_display,
                                                        download_button,
                                                    ],
                                                    queue=False,
                                                )

            with gr.Column(scale=2, min_width=420):
                gr.Markdown("### Параметри та дії")
                age_input = gr.Number(
                    label="Вік",
                    value=None,
                    precision=0,
                    minimum=0,
                    maximum=100,
                    info="Вкажіть вік пацієнта",
                )
                gender_input = gr.Dropdown(
                    label="Стать",
                    choices=["Чоловік", "Жінка"],
                    value=None,
                    info="Виберіть стать пацієнта",
                )
                person_name_input = gr.Textbox(
                    label="Особа",
                    value="",
                    info="Прізвище Імʼя",
                )
                patient_code_input = gr.Textbox(
                    label="Код пацієнта",
                    value="",
                )
                activity_level_radio = gr.Radio(
                    label="Рівень активності пацієнта",
                    choices=[
                        ("Елітний спорт", "elite"),
                        ("Рекреаційний спорт", "recreational"),
                        ("Низька активність", "low"),
                    ],
                    value="low",
                )

                with gr.Row():
                    upload_button = gr.UploadButton(
                        "Додати файли",
                        file_count="multiple",
                        file_types=[".pdf", ".csv"],
                        variant="secondary",
                    )
                    clear_button = gr.Button("Очистити список")

                process_button = gr.Button("Проаналізувати", variant="primary")
                download_button = gr.DownloadButton(
                    "Завантажити звіт (.docx)",
                    value=None,
                    variant="secondary",
                    visible=False,
                )

                warning_display = gr.HTML(visible=False)

        person_name_input.change(
            fn=_set_manual_person_name,
            inputs=[person_name_input, ui_refresh_token],
            outputs=[manual_person_name_state, ui_refresh_token],
            queue=False,
        )

        upload_button.upload(
            fn=add_files_to_list,
            inputs=[
                upload_button,
                file_list_state,
                pushup_type_overrides_state,
                manual_test_overrides_state,
                ui_refresh_token,
            ],
            outputs=[
                file_list_state,
                pushup_type_overrides_state,
                manual_test_overrides_state,
                ui_refresh_token,
                warning_display,
                download_button,
            ],
        )
        (
            clear_button.click(
                fn=clear_all_files,
                inputs=[ui_refresh_token],
                outputs=[
                    file_list_state,
                    pushup_type_overrides_state,
                    manual_test_overrides_state,
                    ui_refresh_token,
                    warning_display,
                    download_button,
                ],
            ).then(
                fn=_reset_person_name,
                inputs=[ui_refresh_token],
                outputs=[
                    person_name_input,
                    manual_person_name_state,
                    patient_code_input,
                    ui_refresh_token,
                ],
                queue=False,
            )
        )
        (
            process_button.click(
                fn=_lock_ui,
                inputs=[],
                outputs=[
                    upload_button,
                    clear_button,
                    process_button,
                    age_input,
                    gender_input,
                    person_name_input,
                    patient_code_input,
                    activity_level_radio,
                    download_button,
                ],
            )
            .then(
                fn=process_files,
                inputs=[
                    file_list_state,
                    age_input,
                    gender_input,
                    activity_level_radio,
                    pushup_type_overrides_state,
                    manual_test_overrides_state,
                    selected_person_key_state,
                    manual_person_name_state,
                    patient_code_input,
                ],
                outputs=[download_button, file_list_state, warning_display],
            )
            .then(
                fn=_reset_person_name_if_ok,
                inputs=[
                    warning_display,
                    person_name_input,
                    patient_code_input,
                    ui_refresh_token,
                ],
                outputs=[
                    person_name_input,
                    manual_person_name_state,
                    patient_code_input,
                    ui_refresh_token,
                ],
            )
            .then(
                fn=_unlock_ui,
                inputs=[],
                outputs=[
                    upload_button,
                    clear_button,
                    process_button,
                    age_input,
                    gender_input,
                    person_name_input,
                    patient_code_input,
                    activity_level_radio,
                    download_button,
                ],
            )
        )

    return demo
