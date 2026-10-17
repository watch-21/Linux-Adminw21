import copy
import sys
import time

import pytest
from app import ActionDialog, Window
from catalog import ACTIONS, PAGES
from monitor import Collector
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QScrollArea
from widgets import ElidedLabel, Graph


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    w = Window(start_sampler=False, start_jobs=False)
    w.refresh_timer.stop()
    w.show()
    app.processEvents()
    yield w, app
    w.close()
    app.processEvents()


def settle(app):
    for _ in range(5):
        app.processEvents()


def wait_jobs(window, app):
    deadline = time.monotonic() + 10
    while window.active_jobs and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert not window.active_jobs


@pytest.mark.parametrize("dims", [(800, 600), (1024, 600), (1366, 768)])
@pytest.mark.parametrize("language", [0, 1])
def test_all_pages_fit_small_windows(ui, dims, language):
    w, app = ui
    w.resize(*dims)
    w.change_language(language)
    settle(app)
    assert (w.width(), w.height()) == dims
    for page, _, _ in PAGES:
        w.navigate(page)
        settle(app)
        container = w.pages[page][0]
        assert container.mapTo(w, container.rect().bottomRight()).x() < w.width()
        for scroll in container.findChildren(QScrollArea):
            assert scroll.horizontalScrollBar().maximum() == 0, page


def test_initial_size_fits_available_screen(ui):
    w, _ = ui
    available = w.screen().availableGeometry()
    assert w.width() <= available.width()
    assert w.height() <= available.height()


def test_compact_sidebar_has_room_for_icons_and_no_horizontal_scroll(ui):
    w, app = ui
    w.resize(800, 600)
    settle(app)
    assert w.sidebar.sizeHintForColumn(0) <= w.sidebar.viewport().width()
    assert w.sidebar.horizontalScrollBar().maximum() == 0


def test_network_numbers_sort_by_rate_and_bytes(ui):
    w, _ = ui
    data = Collector().sample()
    net = next(iter(data["network"].values()))
    data["network"] = {
        name: {**net, "download": value * 1024**2, "rx": value * 1024**3}
        for name, value in [("fast", 100), ("slow", 9), ("middle", 20)]
    }
    w.render(data)
    for column in (2, 4):
        w.network_table.sortItems(column, Qt.AscendingOrder)
        assert [w.network_table.item(i, 0).text() for i in range(3)] == ["slow", "middle", "fast"]
    assert not w.network_table.wordWrap()


def test_session_age_sort_and_selection_follow_identity(ui):
    w, _ = ui
    d = w.dashboard
    now = time.time()
    sessions = [
        {"id": name, "username": name, "start": now - seconds, "groups": [name]}
        for name, seconds in [("hours", 7200), ("minutes", 180), ("day", 86400)]
    ]
    record = {"available": True, "source": "fixture", "sessions": sessions}
    d.update_sessions(record)
    d.session_table.sortItems(4, Qt.AscendingOrder)
    assert [d.session_table.item(i, 0).text() for i in range(3)] == ["minutes", "hours", "day"]
    d.session_table.selectRow(1)
    d.update_sessions(record)
    assert d.selected_session()["username"] == "hours"
    d.update_sessions({**record, "sessions": sessions[1:]})
    assert d.selected_session() is None
    assert not d.session_details.isEnabled()


def test_reused_pid_does_not_select_a_different_process(ui):
    w, _ = ui
    data = Collector().sample()
    assert data["processes"]
    w.render(data)
    w.process_table.selectRow(0)
    selected = w.selected_process()
    changed = copy.deepcopy(data)
    changed["processes"] = [dict(selected, create_time=selected["create_time"] + 100)]
    w.render(changed)
    assert w.selected_process() is None


def test_process_refresh_preserves_scroll_position(ui):
    w, app = ui
    data = Collector().sample()
    proc = data["processes"][0]
    data["processes"] = [dict(proc, pid=10000 + i) for i in range(120)]
    w.navigate("processes")
    w.render(data)
    settle(app)
    bar = w.process_table.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    previous = bar.value()
    assert previous > 0
    w.render(data)
    assert bar.value() == previous


def test_monitor_failure_clears_stale_display_and_recovers(ui):
    w, _ = ui
    data = Collector().sample()
    w.render(data)
    w.monitor_error("fixture failure")
    assert all(card.text() == "—" for card in w.cards.values())
    assert w.process_table.rowCount() == 0
    assert w.network_table.rowCount() == 0
    assert w.dashboard.session_table.rowCount() == 0
    assert not w.dashboard.chart.points
    w.range.setCurrentIndex(1)
    assert not w.dashboard.chart.points
    w.render(data)
    assert w.cards["memory"].text() != "—"
    assert w.dashboard.chart.points


def test_background_user_read_does_not_overwrite_action_result(ui):
    w, app = ui
    output = w.pages["users"][2]
    output.setPlainText("Successful administrative action fixture")
    w.load_users()
    assert output.toPlainText() == "Successful administrative action fixture"
    wait_jobs(w, app)
    assert output.toPlainText() == "Successful administrative action fixture"
    assert w.users_table.rowCount() > 0


def test_older_operation_cannot_replace_newer_result(ui, monkeypatch):
    w, app = ui
    def fake_command(action, args, privileged):
        delay = 0.2 if action == "old" else 0.01
        code = f"import json,time;time.sleep({delay});print(json.dumps({{'ok':True,'output':{action!r}}}))"
        return [sys.executable, "-c", code]
    monkeypatch.setattr("app.command", fake_command)
    output = w.pages["settings"][2]
    w.run_action("old", [], False, output)
    w.run_action("new", [], False, output)
    wait_jobs(w, app)
    assert output.toPlainText() == "✓ new"
    assert len(w.checks) == 2


def test_malformed_backend_envelope_finishes_without_callback_exception(ui, monkeypatch):
    w, app = ui
    monkeypatch.setattr("app.command", lambda *a: [sys.executable, "-c", "print('[]')"])
    output = w.pages["settings"][2]
    w.run_action("fixture", [], False, output)
    wait_jobs(w, app)
    assert output.toPlainText().startswith("⚠")
    assert w.checks[-1]["ok"] is False


def test_language_switch_updates_live_details_and_preserves_search(ui):
    w, _ = ui
    w.render(Collector().sample())
    w.global_search.setText("users")
    w.change_language(1)
    assert "logical cores" in w.dashboard.metric_notes["cpu"].text()
    assert w.sidebar.isRowHidden(0)
    assert not w.sidebar.isRowHidden(2)


def test_light_selection_has_dark_readable_text(ui):
    w, _ = ui
    w.change_theme(1)
    palette = w.palette()
    assert palette.color(QPalette.Highlight).lightness() > palette.color(QPalette.HighlightedText).lightness() + 100


def test_user_dialog_scrolls_form_with_buttons_accessible(ui):
    w, app = ui
    spec = next(s for s in ACTIONS if s[1] == "user.create")
    d = ActionDialog(spec, "de", w)
    d.resize(420, 300)
    d.show()
    settle(app)
    area = d.findChild(QScrollArea)
    buttons = d.findChild(QDialogButtonBox)
    assert area.verticalScrollBar().maximum() > 0
    assert area.horizontalScrollBar().maximum() == 0
    assert buttons.geometry().bottom() < d.height()
    d.close()


def test_graph_short_time_labels_and_missing_series(ui):
    _, app = ui
    graph = Graph(["#4cd1df", "#3cd3a4"])
    graph.times = [100, 100.1]
    assert len(set(graph.time_labels())) == 5
    graph.points = [[1, 2], [None]]
    graph.resize(400, 200)
    graph.show()
    settle(app)
    assert not graph.grab().isNull()
    graph.close()


def test_long_service_names_remain_accessible_without_horizontal_page_scroll(ui):
    w, app = ui
    w.resize(800, 600)
    data = Collector().sample()
    data["system"]["services"] = {"active": 4, "failed": 0, "items": [
        {"unit": "very-long-service-name-" + str(i) * 30 + ".service", "state": "active", "substate": "running"}
        for i in range(4)
    ]}
    w.render(data)
    settle(app)
    area = w.dashboard.findChild(QScrollArea)
    assert area.horizontalScrollBar().maximum() == 0
    labels = w.dashboard.service_panel.findChildren(ElidedLabel)
    assert any("very-long-service" in label.accessibleName() for label in labels)
