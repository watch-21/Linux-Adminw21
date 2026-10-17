"""Native Qt icons, metric panels, table items and charts."""

import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

ACCENTS = ["#4cd1df", "#3cd3a4", "#d3ad6e", "#8f9df5"]
LIGHT_ACCENTS = ["#087e8b", "#087f5b", "#8b5c16", "#5c54bd"]


class NumericItem(QTableWidgetItem):
    def __init__(self, *args):
        super().__init__(*args)
        self._sort_value = None

    def setData(self, role, value):
        if role == Qt.UserRole:
            self._sort_value = value
        super().setData(role, value)

    def __lt__(self, other):
        def key(item):
            value = getattr(item, "_sort_value", None)
            if isinstance(value, (int, float)) and math.isfinite(value):
                return (0, value)
            return (1, item.text().casefold())

        # Avoid empty QVariant conversions on older Python/Qt combinations.
        return key(self) < key(other)


class ElidedLabel(QLabel):
    """Constrain long labels while retaining their complete accessible text."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.full_text = ""
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):
        self.full_text = str(text)
        self.setAccessibleName(self.full_text)
        self.setToolTip(self.full_text)
        self._elide()

    def _elide(self):
        available = max(0, self.contentsRect().width() - 16)
        super().setText(self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, available))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


def icon(kind, color="#a3acbd", size=24):
    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen else 1
    pixmap = QPixmap(math.ceil(size * ratio), math.ceil(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    p.setPen(QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if kind == "dashboard":
        for x, y in [(4, 4), (14, 4), (4, 14), (14, 14)]:
            p.drawRoundedRect(QRectF(x, y, 6, 6), 1, 1)
    elif kind in ("users", "groups"):
        p.drawEllipse(QPointF(10, 7), 3, 3)
        path = QPainterPath(QPointF(4, 20))
        path.cubicTo(3, 11, 17, 11, 16, 20)
        p.drawPath(path)
        p.drawArc(QRectF(15, 4, 5, 6), -70 * 16, 220 * 16)
        p.drawArc(QRectF(15, 12, 7, 8), -85 * 16, 180 * 16)
    elif kind in ("services", "storage", "backup"):
        for y in (4, 13):
            p.drawRoundedRect(QRectF(3, y, 18, 7), 1.5, 1.5)
            p.drawPoint(QPointF(6, y + 3.5))
            p.drawLine(QPointF(14, y + 3.5), QPointF(18, y + 3.5))
    elif kind in ("network",):
        p.drawRect(QRectF(9, 3, 6, 5))
        p.drawLine(12, 8, 12, 13)
        p.drawLine(5, 13, 19, 13)
        for x in (3, 10, 17):
            p.drawLine(x + 2, 13, x + 2, 16)
            p.drawRect(QRectF(x, 16, 4, 4))
    elif kind == "security":
        path = QPainterPath(QPointF(12, 3))
        path.lineTo(20, 6)
        path.cubicTo(21, 14, 17, 19, 12, 22)
        path.cubicTo(7, 19, 3, 14, 4, 6)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(8, 12, 11, 15)
        p.drawLine(11, 15, 16, 9)
    elif kind in ("files", "packages"):
        path = QPainterPath(QPointF(3, 7))
        for x, y in [(3, 5), (10, 5), (12, 8), (21, 8), (20, 20), (3, 20), (3, 7)]:
            path.lineTo(x, y)
        p.drawPath(path)
    elif kind in ("settings",):
        p.drawEllipse(QPointF(12, 12), 6, 6)
        p.drawEllipse(QPointF(12, 12), 2, 2)
        for i in range(8):
            angle = i * math.pi / 4
            p.drawLine(
                QPointF(12 + 7 * math.cos(angle), 12 + 7 * math.sin(angle)),
                QPointF(12 + 10 * math.cos(angle), 12 + 10 * math.sin(angle)),
            )
    elif kind == "processes":
        for y, length in [(5, 14), (12, 10), (19, 16)]:
            p.drawPoint(QPointF(3, y))
            p.drawLine(7, y, length + 5, y)
    else:
        p.drawRoundedRect(QRectF(5, 3, 14, 18), 1, 1)
        for y in (8, 12, 16):
            p.drawLine(8, y, 16, y)
    p.end()
    return QIcon(pixmap)


class Panel(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)
        self.header = QHBoxLayout()
        self.title = ElidedLabel(title)
        self.title.setObjectName("panelTitle")
        self.header.addWidget(self.title, 1)
        self.body.addLayout(self.header)


class Graph(QWidget):
    hovered = Signal(object)

    def __init__(self, colors, parent=None, maximum=None, compact=False):
        super().__init__(parent)
        self.colors, self.maximum, self.compact = colors, maximum, compact
        self.points, self.times = [], []
        self.light = False
        self.hover_time = None
        self.hover_index = None
        self.series_names, self.unit = [], ""
        self.setMouseTracking(not compact)
        self.setMinimumHeight(18 if compact else 150)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def plot_rect(self):
        return (
            QRectF(self.rect()).adjusted(1, 5, -1, -5)
            if self.compact else QRectF(self.rect()).adjusted(57, 12, -27, -27)
        )

    def mouseMoveEvent(self, event):
        rect = self.plot_rect()
        if self.compact or not rect.contains(event.position()) or not self.times or len(self.times) != len(self.points):
            self.clear_hover()
            return
        fraction = (event.position().x() - rect.left()) / max(1, rect.width())
        target = self.times[0] + fraction * (self.times[-1] - self.times[0])
        self.hover_time = target
        self.refresh_hover()

    def refresh_hover(self):
        if self.hover_time is None or not self.times or len(self.times) != len(self.points):
            return
        self.hover_index = min(range(len(self.times)), key=lambda i: abs(self.times[i] - self.hover_time))
        values = self.points[self.hover_index]
        self.hovered.emit({"values": values, "index": self.hover_index, "time": self.times[self.hover_index]})
        self.update()

    def clear_hover(self):
        self.hover_index = self.hover_time = None
        self.hovered.emit(None)
        self.update()

    def leaveEvent(self, event):
        self.clear_hover()
        super().leaveEvent(event)

    def time_labels(self):
        if len(self.times) < 2:
            return []
        span = max(0, self.times[-1] - self.times[0])
        if not span:
            return []
        labels = []
        for i in range(5):
            elapsed = span * (1 - i / 4)
            label = f"−{elapsed / 60:.1f}m" if elapsed >= 60 else f"−{elapsed:.2g}s"
            labels.append(label if elapsed else "0s")
        return labels

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.plot_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        valid = [v for point in self.points for v in point if v is not None and math.isfinite(v)]
        peak = max(valid, default=0)
        max_value = self.maximum or (peak * 1.12 if peak > 0 else 1)
        if not self.compact:
            for i in range(5):
                y = rect.bottom() - i * rect.height() / 4
                p.setPen(QPen(QColor("#cbd3dd" if self.light else "#3b4350"), 0.7, Qt.DashLine))
                p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                p.setPen(QColor("#657083" if self.light else "#8994a5"))
                tick = max_value * i / 4
                if tick >= 1000000:
                    label = f"{tick / 1000000:.1f}M"
                elif tick >= 10000:
                    label = f"{tick / 1000:.1f}k"
                else:
                    label = f"{tick:.0f}" if max_value >= 10 else f"{tick:.2f}" if max_value >= 0.1 else f"{tick:.1e}"
                p.drawText(
                    QRectF(0, y - 8, 49, 16),
                    Qt.AlignRight | Qt.AlignVCenter,
                    label,
                )
            labels = self.time_labels()
            if labels:
                for i, label in enumerate(labels):
                    x = rect.left() + i * rect.width() / 4
                    p.drawText(QRectF(x - 22, rect.bottom() + 6, 45, 15), Qt.AlignCenter, label)
        if len(self.points) < 2 or not valid:
            p.setPen(QColor("#8d99aa"))
            p.drawText(rect, Qt.AlignCenter, "—")
            return
        for column, color in enumerate(self.colors):
            stroke = QPainterPath()
            area = QPainterPath()
            connected = False
            for index, row in enumerate(self.points):
                value = row[column] if column < len(row) else None
                if value is None or not math.isfinite(value):
                    connected = False
                    continue
                if len(self.times) == len(self.points) and self.times[-1] > self.times[0]:
                    fraction = (self.times[index] - self.times[0]) / (self.times[-1] - self.times[0])
                else:
                    fraction = index / (len(self.points) - 1)
                point = QPointF(
                    rect.left() + rect.width() * fraction,
                    rect.bottom() - rect.height() * min(value, max_value) / max_value,
                )
                if not connected:
                    stroke.moveTo(point)
                    area.moveTo(point.x(), rect.bottom())
                    area.lineTo(point)
                else:
                    stroke.lineTo(point)
                    area.lineTo(point)
                next_row = self.points[index + 1] if index < len(self.points) - 1 else []
                next_value = next_row[column] if column < len(next_row) else None
                next_missing = next_value is None or not math.isfinite(next_value)
                if next_missing:
                    area.lineTo(point.x(), rect.bottom())
                    area.closeSubpath()
                connected = True
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            top = QColor(color)
            top.setAlpha(45 if len(self.colors) > 1 else 55)
            bottom = QColor(color)
            bottom.setAlpha(1)
            gradient.setColorAt(0, top)
            gradient.setColorAt(1, bottom)
            p.fillPath(area, gradient)
            p.setPen(QPen(QColor(color), 1.4 if self.compact else 2.1))
            p.drawPath(stroke)
        if self.hover_index is not None and self.hover_index < len(self.points) and len(self.times) == len(self.points):
            index = self.hover_index
            span = self.times[-1] - self.times[0]
            fraction = (self.times[index] - self.times[0]) / span if span else 0
            x = rect.left() + rect.width() * fraction
            p.setPen(QPen(QColor("#6c819b" if self.light else "#a6b8cc"), 1, Qt.DashLine))
            p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            for column, value in enumerate(self.points[index]):
                if column < len(self.colors) and value is not None and math.isfinite(value):
                    p.setBrush(QColor(self.colors[column]))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(x, rect.bottom() - rect.height() * min(value, max_value) / max_value), 4, 4)


def duration(epoch):
    if epoch is None:
        return "—"
    seconds = max(0, int(time.time() - epoch))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return f"{days}d {hours}h" if days else f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
