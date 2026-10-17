"""Native interaction controls shared by the dashboard and action pages."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from widgets import ElidedLabel, Panel, icon


def pressed(widget, active):
    widget._pressed = active
    widget.setProperty("down", active)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class InteractivePanel(Panel):
    activated = Signal()

    def __init__(self):
        super().__init__()
        self.setProperty("interactive", True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pressed = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pressed(self, True)
            self.setFocus(Qt.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        activate = self._pressed and self.rect().contains(event.position().toPoint())
        pressed(self, False)
        if event.button() == Qt.LeftButton and activate:
            self.activated.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if not event.isAutoRepeat() and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class SegmentedControl(QWidget):
    changed = Signal(int)

    def __init__(self, labels):
        super().__init__()
        self.setObjectName("segments")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.group = QButtonGroup(self)
        self.buttons = []
        for index, label in enumerate(labels):
            button = QPushButton(label)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self.group.addButton(button, index)
            self.buttons.append(button)
            layout.addWidget(button, 1)
        self.group.idClicked.connect(self.changed)
        self.set_index(0)

    def set_index(self, index):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)


class ActionTile(QFrame):
    activated = Signal()

    def __init__(self, spec):
        super().__init__()
        self.spec = spec
        self.setObjectName("actionTile")
        self.setProperty("administrative", spec[5])
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pressed = False
        self.setMinimumHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)
        self.glyph = QLabel()
        self.glyph.setFixedSize(26, 26)
        layout.addWidget(self.glyph)
        texts = QVBoxLayout()
        texts.setSpacing(5)
        self.title = ElidedLabel()
        self.title.setObjectName("actionTitle")
        self.caption = ElidedLabel()
        self.caption.setObjectName("muted")
        texts.addWidget(self.title)
        texts.addWidget(self.caption)
        layout.addLayout(texts, 1)
        arrow = QLabel("›")
        arrow.setObjectName("actionArrow")
        layout.addWidget(arrow)

    def translate(self, language):
        title = self.spec[2 if language == "de" else 3]
        self.title.setText(title)
        self.caption.setText(
            ("Mit Bestätigung" if language == "de" else "Confirmation required")
            if self.spec[5] else ("Nur ansehen" if language == "de" else "Read only")
        )
        self.setAccessibleName(title)
        self.setToolTip(title + " · " + self.caption.full_text)

    def set_accent(self, color):
        self.glyph.setPixmap(icon(self.spec[0], color, 26).pixmap(QSize(26, 26)))

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.LeftButton:
            pressed(self, True)
            self.setFocus(Qt.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        activate = self._pressed and self.rect().contains(event.position().toPoint())
        pressed(self, False)
        if self.isEnabled() and event.button() == Qt.LeftButton and activate:
            self.activated.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.isEnabled() and not event.isAutoRepeat() and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


QUICK_ACTIONS = {
    "groups": ["groups.list", "group.create", "group.add", "group.remove"],
    "packages": ["packages.list", "packages.search", "packages.updates", "package.install"],
    "services": ["services.list", "services.logs", "service.start", "service.restart"],
    "network": ["network.info", "network.ping"],
    "files": ["files.list", "files.find", "files.size", "file.mkdir"],
    "backup": ["backup.create", "backup.verify", "backup.preview", "backup.restore"],
    "cron": ["cron.list", "cron.add", "cron.edit", "cron.toggle"],
    "security": ["security.inspect", "firewall.add", "firewall.remove"],
}


class ActionShelf(QWidget):
    def __init__(self, page, specs, callback):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.tiles = []
        self.columns = 0
        for action in QUICK_ACTIONS.get(page, []):
            spec = next(s for s in specs if s[1] == action)
            tile = ActionTile(spec)
            tile.activated.connect(lambda s=spec: callback(s))
            self.tiles.append(tile)
        self.reflow()

    def reflow(self):
        columns = 1 if self.width() < 480 else 2
        if columns == self.columns:
            return
        self.columns = columns
        for tile in self.tiles:
            self.grid.removeWidget(tile)
        for index, tile in enumerate(self.tiles):
            self.grid.addWidget(tile, index // columns, index % columns)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if columns == 2 else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()
