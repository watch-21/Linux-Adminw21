import os
import pathlib
import subprocess
import sys
import time

import pytest
from app import Window
from catalog import ACTIONS
from controls import ActionShelf
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog
from widgets import NumericItem


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    w = Window(start_sampler=False, start_jobs=False)
    w.refresh_timer.stop()
    w.resize(1440, 960)
    w.show()
    for _ in range(4):
        app.processEvents()
    yield w, app
    w.close()
    app.processEvents()


def wait(w, app):
    end = time.monotonic() + 5
    while w.active_jobs and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    assert not w.active_jobs


def test_metric_cards_and_keyboard_switch_activity(ui):
    w, app = ui
    QTest.mouseClick(w.cards["network"], Qt.LeftButton)
    app.processEvents()
    assert w.dashboard.mode.currentIndex() == 1
    assert w.dashboard.metric_panels["network"].property("selected")
    assert not w.dashboard.metric_panels["cpu"].property("selected")
    QTest.keyClick(w.dashboard.metric_panels["disk"], Qt.Key_Space)
    assert w.dashboard.mode.currentIndex() == 2


def test_range_segments_stay_synced_with_history_control(ui):
    w, _ = ui
    buttons = w.dashboard.segments.buttons
    QTest.mouseClick(buttons[1], Qt.LeftButton)
    assert w.range.currentIndex() == 1
    w.range.setCurrentIndex(3)
    assert buttons[3].isChecked()
    assert sum(b.isChecked() for b in buttons) == 1


def test_chart_hover_reports_real_selected_sample(ui):
    w, app = ui
    chart = w.dashboard.chart
    chart.points = [[20, 40], [70, 60]]
    chart.times = [100, 200]
    chart.series_names, chart.unit = ["CPU", "RAM"], " %"
    rect = chart.plot_rect()
    QTest.mouseMove(chart, QPoint(int(rect.right() - 1), int(rect.center().y())))
    app.processEvents()
    assert chart.hover_index == 1
    assert "70.0" in w.dashboard.hover_readout.full_text
    assert "60.0" in w.dashboard.hover_readout.full_text
    chart.clear_hover()
    assert chart.hover_index is None


def test_action_tile_dispatches_matching_action_and_supports_keyboard(ui, monkeypatch):
    w, app = ui
    calls = []
    monkeypatch.setattr(w, "open_action", lambda spec, page: calls.append((spec[1], page)))
    w.navigate("groups")
    app.processEvents()
    tile = w.action_shelves["groups"].tiles[0]
    QTest.mouseClick(tile.title, Qt.LeftButton)
    QTest.keyClick(tile, Qt.Key_Return)
    assert calls == [(tile.spec[1], "groups")] * 2


def test_read_only_action_without_fields_runs_without_empty_dialog(ui, monkeypatch):
    w, _ = ui
    calls = []
    monkeypatch.setattr(w, "run_action", lambda *args, **kw: calls.append(args))
    monkeypatch.setattr("app.ActionDialog", lambda *a: pytest.fail("Read-only action should not open an empty form"))
    w.open_action(next(s for s in ACTIONS if s[1] == "groups.list"), "groups")
    assert calls[0][:3] == ("groups.list", [], False)


def test_busy_action_is_not_submitted_twice_and_controls_recover(ui, monkeypatch):
    w, app = ui
    monkeypatch.setattr("app.command", lambda *a: [sys.executable, "-c", "import time;time.sleep(.15);print('{\"ok\":true,\"output\":\"done\"}')"])
    spec = next(s for s in ACTIONS if s[1] == "groups.list")
    tile = w.action_shelves["groups"].tiles[0]
    w.open_action(spec, "groups")
    w.open_action(spec, "groups")
    assert len(w.active_jobs) == 1
    assert not tile.isEnabled()
    assert w.live_badge.property("state") == "busy"
    wait(w, app)
    assert tile.isEnabled()
    assert w.live_badge.property("state") == "ready"
    assert w.notification.isVisible()
    w.notification_view.click()
    assert w.stack.currentIndex() == 3
    w.run_action("next", [], False, w.pages["groups"][2])
    assert w.notification.isHidden()
    wait(w, app)
    assert w.notification.isVisible()


def test_theme_shortcut_keeps_settings_in_sync(ui):
    w, _ = ui
    w.theme_button.click()
    assert w.preferences["theme"] == "light"
    assert w.theme_combo.currentIndex() == 1
    w.theme_button.click()
    assert w.preferences["theme"] == "dark"
    assert w.theme_combo.currentIndex() == 0


def test_selected_user_prefills_action_and_filter_disables_context(ui, monkeypatch):
    w, _ = ui
    w.users_table.setSortingEnabled(False)
    w.users_table.setRowCount(1)
    for col, value in enumerate(["alice", "1000", "1000", "Alice", "/home/alice", "/bin/bash"]):
        w.users_table.setItem(0, col, NumericItem(value))
    w.users_table.selectRow(0)
    assert w.user_password_button.isEnabled()
    captured = []
    def reject(dialog):
        captured.append(dialog.arguments()[0])
        return QDialog.Rejected
    monkeypatch.setattr("app.ActionDialog.exec", reject)
    w.open_user_action("user.password")
    assert captured == ["alice"]
    assert not w.active_jobs
    w.user_filter.setText("no-such-user")
    assert not w.user_details_button.isEnabled()
    assert not w.user_password_button.isEnabled()


def test_shelves_and_hints_translate(ui):
    w, _ = ui
    w.change_language(1)
    tile = w.action_shelves["groups"].tiles[0]
    assert tile.title.full_text == "List groups"
    assert tile.caption.full_text == "Read only"
    assert "Browse accounts" in w.page_hints["users"].text()
    w.change_language(0)
    assert tile.caption.full_text == "Nur ansehen"


def test_shelf_reflows_instead_of_clipping_actions(ui):
    w, app = ui
    shelf = w.action_shelves["groups"]
    w.navigate("groups")
    w.resize(800, 600)
    for _ in range(4):
        app.processEvents()
    assert shelf.columns in (1, 2)
    assert all(tile.geometry().right() < shelf.width() for tile in shelf.tiles)
    assert isinstance(shelf, ActionShelf)


def test_multiple_operations_share_progress_without_expanding_window(ui, monkeypatch):
    w, app = ui
    w.resize(800, 600)
    monkeypatch.setattr("app.command", lambda *a: [sys.executable, "-c", "import time;time.sleep(.15);print('{\"ok\":true,\"output\":\"done\"}')"])
    for i in range(8):
        w.run_action("fixture-" + str(i), [], False, w.pages["settings"][2])
    app.processEvents()
    assert w.width() == 800
    assert w.job_progress.isVisible()
    wait(w, app)
    assert w.job_progress.isHidden()


def test_window_and_empty_state_delete_cleanly(tmp_path):
    root = pathlib.Path(__file__).resolve().parents[1]
    env = dict(os.environ, XDG_CONFIG_HOME=str(tmp_path))
    env["PYTHONPATH"] = os.pathsep.join([str(root / "gui"), str(root / "backend"), env.get("PYTHONPATH", "")])
    result = subprocess.run([
        sys.executable, "-c",
        "from PySide6.QtCore import QCoreApplication,QEvent;"
        "from PySide6.QtWidgets import QApplication;from app import Window;"
        "app=QApplication([]);w=Window(start_sampler=False,start_jobs=False);"
        "w.show();app.processEvents();w.close();w.deleteLater();"
        "QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()",
    ], env=env, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "already deleted" not in result.stderr
