"""Exercise the frozen Qt runtime without importing the NEOMapper stack."""

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QDateTime,
    QEventLoop,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


app = QApplication([])
label = QLabel("Qt runtime OK")
label.setWindowTitle("NEOMapper Qt smoke test")
label.show()
QTimer.singleShot(10_000, app.quit)
raise SystemExit(app.exec())
