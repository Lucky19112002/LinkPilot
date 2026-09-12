from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from config import load_config
from ui.about import AboutPage
from ui.benchmark import BenchmarkPage
from ui.dashboard import DashboardPage
from ui.diagnostics import DiagnosticsPage
from ui.logs import LogsPage
from ui.models import ModelsPage
from ui.settings import SettingsPage
from ui.setup_wizard import SetupWizard
from ui.release import ReleasePage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.setWindowTitle("LinkPilot")
        self.resize(900, 620)

        tabs = QTabWidget()
        tabs.addTab(DashboardPage(self.config), "Dashboard")
        tabs.addTab(SettingsPage(self.config), "Settings")
        tabs.addTab(ModelsPage(self.config), "Models")
        tabs.addTab(LogsPage(), "Logs")
        tabs.addTab(SetupWizard(), "Setup")
        tabs.addTab(DiagnosticsPage(self.config), "Diagnostics")
        tabs.addTab(BenchmarkPage(self.config), "Benchmark")
        tabs.addTab(ReleasePage(self.config), "Release")
        tabs.addTab(AboutPage(self.config), "About")
        self.setCentralWidget(tabs)
        if not self.config.first_launch_complete:
            tabs.setCurrentIndex(0)

    def closeEvent(self, event) -> None:
        tabs = self.centralWidget()
        for index in range(tabs.count()):
            widget = tabs.widget(index)
            cleanup = getattr(widget, "cleanup", None)
            if cleanup:
                cleanup()
        super().closeEvent(event)
