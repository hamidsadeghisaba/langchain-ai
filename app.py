from __future__ import annotations

import uuid
import streamlit as st
import base64 
from pathlib import Path

from service.model.task_models import Task, TaskStage, TaskStatus
from service.task_service import TaskWorkflowRuntime


FONT_DIR = Path(__file__).parent / "assets" / "fonts"

regular_font = base64.b64encode(
    (FONT_DIR / "Vazirmatn-Regular.woff2").read_bytes()
).decode("utf-8")

bold_font = base64.b64encode(
    (FONT_DIR / "Vazirmatn-Bold.woff2").read_bytes()
).decode("utf-8")

st.markdown(
    f"""
    <style>
        @font-face {{
            font-family: 'Vazirmatn';
            src: url(data:font/woff2;base64,{regular_font}) format('woff2');
            font-weight: 400;
            font-style: normal;
        }}

        @font-face {{
            font-family: 'Vazirmatn';
            src: url(data:font/woff2;base64,{bold_font}) format('woff2');
            font-weight: 700;
            font-style: normal;
        }}

        /* فونت پیش‌فرض رابط کاربری */
        html,
        body,
        .stApp,
        .stApp *,
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] * {{
            font-family: 'Vazirmatn', sans-serif !important;
        }}

        /* راست‌چین کردن محتوای فارسی */
        .stApp {{
            direction: rtl;
            text-align: right;
        }}

        /* فیلدهای ورودی */
        input,
        textarea {{
            direction: rtl;
            text-align: right;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.set_page_config(
    page_title="AI Development Workflow",
    page_icon="🤖",
    layout="wide",
)

st.markdown("""
<style>
    .stApp {
        direction: rtl;
        text-align: right;
    }

    p, h1, h2, h3, h4, h5, h6, label, li {
        direction: rtl;
        text-align: right;
    }

    input, textarea, [data-baseweb="select"] {
        direction: rtl;
        text-align: right;
    }

    [data-testid="stChatMessage"] {
        direction: rtl;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_runtime() -> TaskWorkflowRuntime:
    # One process-owned graph/checkpointer is reused by every Streamlit rerun.
    return TaskWorkflowRuntime.create()


def run_action(action, success_message: str) -> None:
    try:
        with st.spinner("در حال اجرا ..."):
            action()
    except Exception as error:
        st.session_state.flash = (
            "error",
            f"{type(error).__name__}: {error}",
        )
    else:
        st.session_state.flash = ("success", success_message)
    st.rerun()


def render_results(task: Task) -> None:
    if task.analysis_result:
        with st.expander("گزارش تحلیل", expanded=False):
            st.markdown(task.analysis_result)
    if task.development_result:
        with st.expander("گزارش توسعه کد", expanded=False):
            st.markdown(task.development_result)
    if task.test_result:
        with st.expander("گزارش تست", expanded=False):
            st.markdown(task.test_result)


def render_task(
    task: Task,
    runtime: TaskWorkflowRuntime,
    *,
    stage: TaskStage,
) -> None:
    status_text = task.status.value
    if task.awaiting_approval:
        status_text = "منتظر تایید"

    label = (
        f"{task.title} · {status_text} · priority {task.priority}"
    )
    with st.expander(label, expanded=task.awaiting_approval):
        st.write(task.description)
        st.caption(
            f"Task: {task.task_id}  |  LangGraph thread: {task.thread_id}  |  "
            f"Retries: {task.retry_count}  |  Recoveries: {task.recovery_count}"
        )

        if task.error_message:
            st.error(task.error_message)

        render_results(task)

        if task.awaiting_approval:
            approval_col, rejection_col = st.columns(2)
            with approval_col:
                if st.button(
                    "تایید تحلیل",
                    key=f"approve-{task.task_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    run_action(
                        lambda: runtime.service.approve_task(task.task_id),
                        "Analysis approved. Developer and Tester stages finished.",
                    )
            with rejection_col:
                if st.button(
                    "عدم تایید",
                    key=f"reject-{task.task_id}",
                    use_container_width=True,
                ):
                    run_action(
                        lambda: runtime.service.reject_task(task.task_id),
                        "Analysis rejected. The task is available for retry.",
                    )

        elif task.status is TaskStatus.PENDING:
            if st.button(
                f"اجرای {stage.value.title()} ",
                key=f"run-{task.task_id}",
                type="primary",
            ):
                run_action(
                    lambda: runtime.service.run_task(task.task_id),
                    f"{stage.value.title()} stage finished.",
                )

        elif task.status is TaskStatus.FAILED:
            if st.button(
                "تلاش مجدد",
                key=f"retry-{task.task_id}",
                type="primary",
            ):
                run_action(
                    lambda: runtime.service.retry_task(task.task_id),
                    "Task returned to PENDING without creating a duplicate.",
                )

        elif task.status is TaskStatus.RUNNING:
            st.info(
                " تسک به حالت اجرا درامد. در صورت بروز مشکل و توقف آن مجددا در صف انتظار قرار خواهد گرفت."
            )


st.title("دستیار توسعه هوشمند")
st.markdown(
    """
    <div style="font-size: 24px; font-weight: 600; direction: rtl; text-align: right;">
        تست → کد → تحلیل
    </div>
    """,
    unsafe_allow_html=True
)

runtime = get_runtime()

if "flash" in st.session_state:
    flash_type, flash_message = st.session_state.pop("flash")
    if flash_type == "error":
        st.error(flash_message)
    else:
        st.success(flash_message)

summary_columns = st.columns(4)
all_tasks = runtime.repository.list_tasks()
pending_dev = runtime.repository.list_pending_tasks(TaskStage.DEVELOPER)
pending_test = runtime.repository.list_pending_tasks(TaskStage.TESTER)
pending_analysis = runtime.repository.list_pending_tasks(TaskStage.ANALYZER)
with summary_columns[0]:
    st.metric("تعداد تسک‌ها", len(all_tasks))
with summary_columns[1]:
    st.metric("صف تحلیل", len(pending_analysis))
with summary_columns[2]:
    st.metric("صف کد", len(pending_dev))
with summary_columns[3]:
    st.metric("صف تست", len(pending_test))

submit_tab, analyzer_tab, developer_tab, tester_tab = st.tabs(
    ["ایجاد تسک", "صف تحلیل", "صف کد", "صف تست"]
)

with submit_tab:
    st.subheader("توسعه تسک")
    with st.form("task-submission", clear_on_submit=True):
        title = st.text_input(
            "عنوان",
            placeholder="عنوان تسک",
        )
        description = st.text_area(
            "نیازمندی‌ها",
            height=180,
            placeholder="روایت...",
        )
        # priority = st.number_input(
        #     "Priority",
        #     min_value=0,
        #     max_value=100,
        #     value=10,
        #     step=1,
        # )
        submitted = st.form_submit_button(
            "ایجاد تسک",
            type="primary",
        )

    if submitted:
        submission_key = st.session_state.setdefault(
            "submission_key",
            uuid.uuid4().hex,
        )
        try:
            task = runtime.service.create_task(
                title=title,
                description=description,
                priority=0,
                submission_key=submission_key,
            )
            st.session_state.pop("submission_key", None)
            run_action(
                lambda: runtime.service.run_task(task.task_id),
                "تحلیل پایان یافت و تسک به صف توسعه کد منتقل شد.",
            )
        except Exception as error:
            st.session_state.flash = (
                "error",
                f"{type(error).__name__}: {error}",
            )
            st.rerun()

with analyzer_tab:
    st.subheader("صف تحلیل")
    analyzer_tasks = runtime.repository.list_tasks(stage=TaskStage.ANALYZER)
    if not analyzer_tasks:
        st.info("صف تحلیل خالی است.")
    for task in analyzer_tasks:
        render_task(task, runtime, stage=TaskStage.ANALYZER)

with developer_tab:
    st.subheader("صف توسعه کد")
    developer_tasks = runtime.repository.list_tasks(stage=TaskStage.DEVELOPER)
    if not developer_tasks:
        st.info("صف توسعه کد خالی است")
    for task in developer_tasks:
        render_task(task, runtime, stage=TaskStage.DEVELOPER)

with tester_tab:
    st.subheader("صف تست")
    tester_tasks = runtime.repository.list_tasks(stage=TaskStage.TESTER)
    if not tester_tasks:
        st.info("صف تست خالی است")
    for task in tester_tasks:
        render_task(task, runtime, stage=TaskStage.TESTER)

st.divider()
if st.button("بروزرسانی صف‌ها"):
    st.rerun()

# st.caption(
    # "Task metadata and LangGraph checkpoints are stored in "
    # f"`{runtime.repository.db_path}`."
# )
