import os
import pathlib
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import settings
from app import ActionDialog, NumericItem, Window
from catalog import ACTIONS, FIELD_DE, PAGES
from monitor import Collector
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog


@pytest.fixture(scope="session")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(application, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    w = Window(start_sampler=False, start_jobs=False)
    w.resize(1440, 960)
    w.refresh_timer.stop()
    # Avoid the asynchronous initial user read during deterministic UI tests.
    w.load_users = lambda: None
    w.show()
    application.processEvents()
    yield w
    w.close()
    application.processEvents()


def test_sidebar_and_languages(window, application):
    assert window.sidebar.count() == len(PAGES)
    for i in range(len(PAGES)):
        window.sidebar.setCurrentRow(i)
        application.processEvents()
        assert window.stack.currentIndex() == i
    window.change_language(1)
    assert window.sidebar.item(0).text() == "Overview"
    window.change_language(0)
    assert window.sidebar.item(0).text() == "Übersicht"


def test_password_confirmation(application, window):
    spec = next(s for s in ACTIONS if s[1] == "user.create")
    dialog = ActionDialog(spec, "de", window)
    dialog.password.setText("secret:with:colons")
    dialog.confirm.setText("wrong")
    dialog.validate()
    assert dialog.result() != QDialog.Accepted
    assert dialog.notice.text()
    dialog.confirm.setText("secret:with:colons")
    dialog.validate()
    assert dialog.result() == QDialog.Accepted
    assert dialog.arguments()[1] == "yes"


def test_table_numeric_sort(application):
    a, b = NumericItem("2"), NumericItem("100")
    a.setData(Qt.UserRole, 2)
    b.setData(Qt.UserRole, 100)
    assert a < b


def test_repeated_mixed_table_sort_does_not_crash():
    # Isolate a native binding crash so older Python versions report a failed
    # regression instead of aborting the whole suite.
    root = pathlib.Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root / "gui"), str(root / "backend"), env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget
from app import NumericItem
app = QApplication([])
table = QTableWidget(16, 2)
for row in range(16):
    table.setItem(row, 0, NumericItem('name-' + str(15-row)))
    item = NumericItem(str(row))
    item.setData(Qt.UserRole, row)
    table.setItem(row, 1, item)
for iteration in range(400):
    order = Qt.AscendingOrder if iteration % 2 else Qt.DescendingOrder
    table.sortItems(0, order)
    table.sortItems(1, order)
table.sortItems(1, Qt.AscendingOrder)
assert [int(table.item(row, 1).text()) for row in range(16)] == list(range(16))
""",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_live_render_search_history(window, application):
    collector = Collector()
    data = collector.sample()
    time.sleep(0.05)
    data = collector.sample()
    for _ in range(20):
        window.render(data)
        application.processEvents()
    assert window.process_table.rowCount() > 0
    assert "—" not in window.cards["memory"].text()
    assert "processes" not in window.history[0]
    window.search.setText("DOES-NOT-EXIST-451923")
    assert window.process_table.rowCount() == 0
    window.search.clear()
    assert window.process_table.rowCount() > 0
    window.resize(950, 650)
    application.processEvents()
    assert window.width() == 950


def test_settings_atomic_private(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    settings.save({"language": "en", "theme": "light"})
    assert settings.read() == {"language": "en", "theme": "light"}
    assert settings.config_path().stat().st_mode & 0o777 == 0o600
    settings.config_path().write_text("invalid")
    assert settings.read()["language"] == "de"


def test_catalog_translation_and_unique_actions():
    assert len({a[1] for a in ACTIONS}) == len(ACTIONS)
    for spec in ACTIONS:
        assert spec[2] and spec[3]
        for label, _default in spec[4]:
            assert label in FIELD_DE


def test_backend_failure_display_and_cleanup(window, application):
    output = window.pages["settings"][2]
    window.run_action("disallowed", [], False, output)
    deadline = time.monotonic() + 10
    while window.active_jobs and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)
    assert not window.active_jobs
    assert "Unknown or disallowed action" in output.toPlainText()
    assert window.checks[-1]["ok"] is False


def test_action_cancellation(application, window):
    spec = next(s for s in ACTIONS if s[1] == "user.password")
    dialog = ActionDialog(spec, "en", window)
    dialog.password.setText("Never-submitted")
    dialog.reject()
    assert dialog.result() == QDialog.Rejected
    assert not window.active_jobs


def test_live_sessions_groups_and_duplicate_user(window, application):
    records = [
        {
            "id": "2",
            "username": "alex",
            "groups": ["alex", "sudo", "docker"],
            "primary_group": "alex",
            "supplementary_groups": ["sudo", "docker"],
            "type": "wayland",
            "host": None,
            "start": None,
        },
        {
            "id": "3",
            "username": "alex",
            "groups": ["alex", "sudo", "docker"],
            "primary_group": "alex",
            "supplementary_groups": ["sudo", "docker"],
            "type": "SSH",
            "host": "192.168.1.20",
            "start": None,
        },
    ]
    window.dashboard.update_sessions({"available": True, "source": "test fixture", "sessions": records})
    assert window.dashboard.session_table.rowCount() == 2
    assert "1 " in window.dashboard.session_count.text()
    assert "2 " in window.dashboard.session_count.text()
    assert "docker" in window.dashboard.session_table.item(0, 1).text()
    window.dashboard.session_table.selectRow(0)
    assert window.dashboard.selected_session()["username"] == "alex"
    window.dashboard.update_sessions({"available": False, "sessions": []})
    assert window.dashboard.session_table.rowCount() == 0
    assert window.dashboard.session_count.text() == "—"


def test_collapse_navigation_search_and_language(window, application):
    window.toggle_sidebar()
    assert window.nav_panel.width() == 66
    window.change_language(1)
    assert window.sidebar.item(0).text() == ""
    window.toggle_sidebar()
    assert window.sidebar.item(0).text() == "Overview"
    window.global_search.setText("sshd")
    window.search_everywhere()
    assert window.stack.currentIndex() == 1
    assert window.search.text() == "sshd"
    window.global_search.setText("users")
    window.search_everywhere()
    assert window.stack.currentIndex() == 2


def test_monitor_refresh_does_not_overwrite_report(window, application):
    collector = Collector()
    window.report_output.setPlainText("collected report fixture")
    window.render(collector.sample())
    assert window.report_output.toPlainText() == "collected report fixture"


def test_light_theme_and_minimum_size(window, application):
    window.change_theme(1)
    window.resize(950, 650)
    application.processEvents()
    assert window.width() == 950
    assert window.dashboard.chart.light
    window.change_language(1)
    assert window.dashboard.session_panel.title.text() == "Logged-in users"


def test_small_dashboard_reflows_without_page_horizontal_scroll(window, application):
    from PySide6.QtWidgets import QBoxLayout, QScrollArea

    window.resize(950, 650)
    for _ in range(4):
        application.processEvents()
    assert window.dashboard.middle.direction() == QBoxLayout.TopToBottom
    area = window.dashboard.findChild(QScrollArea)
    assert area.horizontalScrollBar().maximum() == 0
    window.resize(1440, 960)
    for _ in range(4):
        application.processEvents()
    assert window.dashboard.middle.direction() == QBoxLayout.LeftToRight
    assert area.horizontalScrollBar().maximum() == 0
