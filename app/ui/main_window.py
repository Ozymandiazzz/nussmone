"""Main window — drag GLB, rotate, process, open output. No motor logic."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QSpinBox,
)

from app import output_root
from app.services.detect import check_environment
from app.services.pipeline_runner import (PipelineResult, package_mode_available,
                                          run_package_pipeline, run_pipeline)


PRESETS = {
    "Sem rotação": (0.0, 0.0, 0.0),
    "Girar X 90": (90.0, 0.0, 0.0),
    "Girar Y 90": (0.0, 90.0, 0.0),
    "Girar Z 90": (0.0, 0.0, 90.0),
}


class PipelineWorker(QThread):
    log_line = Signal(str)
    finished_result = Signal(object)

    def __init__(
        self,
        glb: Path,
        rx: float,
        ry: float,
        rz: float,
        name: str | None = None,
        package_options: tuple[str, str, int, str, str, str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._glb = glb
        self._rx = rx
        self._ry = ry
        self._rz = rz
        self._name = name
        self._package_options = package_options

    def run(self) -> None:
        if self._package_options:
            catalog_name, description, price, mesh_exporter, donor, blend_template = self._package_options
            result = run_package_pipeline(
                self._glb, catalog_name, description, price, mesh_exporter=mesh_exporter,
                donor=Path(donor) if donor else None,
                blend_template=Path(blend_template) if blend_template else None,
                rotate_x=self._rx, rotate_y=self._ry, rotate_z=self._rz,
                log=lambda m: self.log_line.emit(m),
            )
        else:
            result = run_pipeline(
                self._glb, rotate_x=self._rx, rotate_y=self._ry,
                rotate_z=self._rz, name=self._name,
                log=lambda m: self.log_line.emit(m),
            )
        self.finished_result.emit(result)


class DropLineEdit(QLineEdit):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(True)
        self.setPlaceholderText("Arraste um .glb aqui ou use Selecionar…")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".glb"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".glb"):
                self.file_dropped.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CC Studio Desktop Prototype")
        self.resize(760, 720)
        self._worker: PipelineWorker | None = None
        self._last_output: Path | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # Environment
        env_box = QGroupBox("Ambiente")
        env_form = QFormLayout(env_box)
        self.lbl_blender = QLabel()
        self.lbl_template = QLabel()
        self.lbl_output = QLabel()
        self.lbl_ready = QLabel()
        for lbl in (self.lbl_blender, self.lbl_template, self.lbl_output):
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        env_form.addRow("Blender:", self.lbl_blender)
        env_form.addRow("Template:", self.lbl_template)
        env_form.addRow("Saída:", self.lbl_output)
        env_form.addRow("Status:", self.lbl_ready)
        layout.addWidget(env_box)

        # Input
        in_box = QGroupBox("Arquivo GLB")
        in_layout = QVBoxLayout(in_box)
        row = QHBoxLayout()
        self.input_edit = DropLineEdit()
        self.input_edit.file_dropped.connect(self._set_input)
        btn_browse = QPushButton("Selecionar…")
        btn_browse.clicked.connect(self._browse)
        row.addWidget(self.input_edit, 1)
        row.addWidget(btn_browse)
        in_layout.addLayout(row)
        self.drop_hint = QLabel("Solte um .glb na caixa acima.")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(
            "QLabel { border: 1px dashed #888; padding: 28px; color: #555; background: #f7f7f7; }"
        )
        self.drop_hint.setAcceptDrops(True)
        in_layout.addWidget(self.drop_hint)
        layout.addWidget(in_box)

        # Rotation + presets
        rot_box = QGroupBox("Rotação (graus, antes do fit)")
        rot_form = QFormLayout(rot_box)
        self.preset = QComboBox()
        self.preset.addItems(list(PRESETS.keys()))
        self.preset.currentTextChanged.connect(self._apply_preset)
        rot_form.addRow("Preset:", self.preset)

        self.spin_x = QDoubleSpinBox()
        self.spin_y = QDoubleSpinBox()
        self.spin_z = QDoubleSpinBox()
        for spin in (self.spin_x, self.spin_y, self.spin_z):
            spin.setRange(-360.0, 360.0)
            spin.setDecimals(1)
            spin.setSingleStep(90.0)
        rot_form.addRow("Rotate X:", self.spin_x)
        rot_form.addRow("Rotate Y:", self.spin_y)
        rot_form.addRow("Rotate Z:", self.spin_z)
        layout.addWidget(rot_box)

        # Output and catalog fields. The package path is a local experimental mode.
        catalog_box = QGroupBox("Saída")
        catalog_form = QFormLayout(catalog_box)
        self.output_mode = QComboBox()
        self.output_mode.addItem("Modelo .blend + textura", "blend")
        if package_mode_available():
            self.output_mode.addItem("Objeto .package (experimental/local)", "package")
        self.output_mode.currentIndexChanged.connect(self._update_catalog_fields)
        catalog_form.addRow("Formato:", self.output_mode)
        self.catalog_name = QLineEdit()
        self.catalog_name.setPlaceholderText("Nome no catálogo do jogo")
        self.catalog_description = QLineEdit("Criado com CC Studio")
        self.catalog_price = QSpinBox()
        self.catalog_price.setRange(0, 1_000_000)
        self.catalog_price.setValue(1300)
        self.mesh_exporter = QComboBox()
        self.mesh_exporter.addItem("S4S local (fluxo anterior)", "s4s_local")
        self.mesh_exporter.addItem("Independente (experimental)", "independent_local")
        self.donor_path = QLineEdit()
        self.donor_path.setPlaceholderText("Usar padrão ou escolher um .package doador")
        donor_row = QHBoxLayout()
        donor_row.addWidget(self.donor_path, 1)
        self.btn_donor = QPushButton("Selecionar…")
        self.btn_donor.clicked.connect(self._browse_donor)
        donor_row.addWidget(self.btn_donor)
        self.template_path = QLineEdit()
        self.template_path.setPlaceholderText("Usar padrão ou escolher um template .blend")
        template_row = QHBoxLayout()
        template_row.addWidget(self.template_path, 1)
        self.btn_template = QPushButton("Selecionar…")
        self.btn_template.clicked.connect(self._browse_template)
        template_row.addWidget(self.btn_template)
        catalog_form.addRow("Nome:", self.catalog_name)
        catalog_form.addRow("Descrição:", self.catalog_description)
        catalog_form.addRow("Preço (§):", self.catalog_price)
        catalog_form.addRow("Motor de malha:", self.mesh_exporter)
        catalog_form.addRow("Pacote doador:", donor_row)
        catalog_form.addRow("Template:", template_row)
        self.package_note = QLabel("Protótipo local: receita decor_vase. O motor independente não carrega S4S nas etapas de malha.")
        self.package_note.setWordWrap(True)
        catalog_form.addRow("", self.package_note)
        layout.addWidget(catalog_box)

        # Actions
        actions = QHBoxLayout()
        self.btn_process = QPushButton("Processar")
        self.btn_process.setDefault(True)
        self.btn_process.clicked.connect(self._process)
        self.btn_open = QPushButton("Abrir pasta de saída")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_output)
        actions.addWidget(self.btn_process)
        actions.addWidget(self.btn_open)
        layout.addLayout(actions)

        self.status_label = QLabel("Pronto.")
        layout.addWidget(self.status_label)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log, 1)

        self._refresh_env()
        self._apply_preset(self.preset.currentText())
        self._update_catalog_fields()

    def _update_catalog_fields(self) -> None:
        package = self.output_mode.currentData() == "package"
        for widget in (self.catalog_name, self.catalog_description,
                       self.catalog_price, self.mesh_exporter, self.package_note,
                       self.donor_path, self.template_path, self.btn_donor,
                       self.btn_template):
            widget.setEnabled(package)

    def _refresh_env(self) -> None:
        env = check_environment()
        self.lbl_blender.setText(env.blender_label)
        self.lbl_template.setText(env.template_label)
        self.lbl_output.setText(str(output_root()))
        if env.ok:
            self.lbl_ready.setText("OK — pode processar")
            self.lbl_ready.setStyleSheet("color: green;")
            self.btn_process.setEnabled(True)
        else:
            self.lbl_ready.setText("Falha — veja mensagens abaixo")
            self.lbl_ready.setStyleSheet("color: red;")
            self.btn_process.setEnabled(False)
            for m in env.messages:
                self._append(m)

    def _append(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    def _set_input(self, path: str) -> None:
        self.input_edit.setText(path)
        self.drop_hint.setText(Path(path).name)
        self._append(f"Selecionado: {path}")
        if not self.catalog_name.text().strip():
            self.catalog_name.setText(Path(path).stem)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar GLB",
            "",
            "glTF Binary (*.glb)",
        )
        if path:
            self._set_input(path)

    def _browse_donor(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar pacote doador", "",
                                              "Sims 4 Package (*.package)")
        if path:
            self.donor_path.setText(path)

    def _browse_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar template Blender", "",
                                              "Blender (*.blend)")
        if path:
            self.template_path.setText(path)

    def _apply_preset(self, name: str) -> None:
        if name not in PRESETS:
            return
        x, y, z = PRESETS[name]
        self.spin_x.setValue(x)
        self.spin_y.setValue(y)
        self.spin_z.setValue(z)

    def _process(self) -> None:
        path = self.input_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "CC Studio", "Selecione um arquivo .glb.")
            return
        glb = Path(path)
        if not glb.is_file():
            QMessageBox.warning(self, "CC Studio", f"Arquivo não encontrado:\n{path}")
            return

        if self._worker and self._worker.isRunning():
            return

        package_options = None
        if self.output_mode.currentData() == "package":
            catalog_name = self.catalog_name.text().strip()
            if not catalog_name:
                QMessageBox.warning(self, "CC Studio", "Informe o nome do objeto no catálogo.")
                return
            package_options = (catalog_name, self.catalog_description.text(),
                               self.catalog_price.value(), self.mesh_exporter.currentData(),
                               self.donor_path.text().strip(), self.template_path.text().strip())

        self.btn_process.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.status_label.setText("Processando…")
        self._append("---")
        self._append("Iniciando processamento…")

        self._worker = PipelineWorker(
            glb,
            self.spin_x.value(),
            self.spin_y.value(),
            self.spin_z.value(),
            package_options=package_options,
        )
        self._worker.log_line.connect(self._append)
        self._worker.finished_result.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, result: object) -> None:
        assert isinstance(result, PipelineResult)
        self.btn_process.setEnabled(True)
        if result.ok and result.output_dir:
            self._last_output = result.output_dir
            self.btn_open.setEnabled(True)
            self.status_label.setText(f"PASS — {result.message} {result.output_dir}")
            self.status_label.setStyleSheet("color: green;")
            files = []
            if result.package:
                files.append("  CCStudio.package")
            if result.blend:
                files.append(f"  sims_ready.blend")
            if result.basecolor:
                files.append(f"  basecolor.png")
            if result.report:
                files.append("  build_report.json" if result.package else "  report.json")
            if result.log:
                files.append(f"  run.log")
            if files:
                self._append("Arquivos:")
                for f in files:
                    self._append(f)
        else:
            self.status_label.setText(f"FAIL — {result.message}")
            self.status_label.setStyleSheet("color: red;")
            if result.output_dir:
                self._last_output = result.output_dir
                self.btn_open.setEnabled(True)

    def _open_output(self) -> None:
        if not self._last_output or not self._last_output.is_dir():
            return
        path = str(self._last_output)
        if os.name == "nt":
            os.startfile(path)  # noqa: S606 — intentional Explorer open
        else:
            subprocess.Popen(["xdg-open", path])
