import os
import threading
import tempfile
import unittest
from pathlib import Path
from PySide6.QtGui import QImage
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from neomapper.presentation import gui
from neomapper.presentation.gui import NEOMapperMainWindow, application_icon_path


class MainWindowTests(unittest.TestCase):
    def test_time_mode_is_in_settings_and_persists_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                self.assertTrue(window.right_stack.widget(5).isAncestorOf(window.time_mode_combo))
                self.assertFalse(window.right_stack.widget(3).isAncestorOf(window.time_mode_combo))
                window.time_mode_combo.setCurrentText("LOCAL")
                self.assertEqual(gui.load_config()["time"]["mode"], "LOCAL")
            finally:
                window.close()

    def test_animation_defaults_follow_initial_date_and_steps_keep_values_across_languages(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                self.assertEqual(window.anim_start_edit.dateTime(), window.datetime_edit.dateTime())
                self.assertEqual(window.anim_start_edit.dateTime().secsTo(window.anim_end_edit.dateTime()), 86400)
                updated = gui.QDateTime(2028, 2, 29, 22, 15, 0)
                window.datetime_edit.setDateTime(updated)
                self.assertEqual(window.anim_start_edit.dateTime(), updated)
                self.assertEqual(window.anim_end_edit.dateTime(), updated.addSecs(86400))
                window.anim_step_combo.setCurrentIndex(window.anim_step_combo.findData("month"))
                for language, month, week, year in [("PT", "1 mês", "1 semana", "1 ano"), ("ES", "1 mes", "1 semana", "1 año"), ("EN", "1 month", "1 week", "1 year")]:
                    window.language_header_combo.setCurrentText(language)
                    self.assertEqual(window.anim_step_combo.currentData(), "month")
                    self.assertEqual(window.anim_step_combo.currentText(), month)
                    self.assertEqual(window.anim_step_combo.itemText(window.anim_step_combo.findData(10080)), week)
                    self.assertEqual(window.anim_step_combo.itemText(window.anim_step_combo.findData("year")), year)
            finally:
                window.close()
    def test_generation_limits_default_to_500_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                self.assertEqual(window.animation_frame_limit.value(), 500)
                self.assertEqual(window.ephemeris_row_limit.value(), 500)
                window.animation_frame_limit.setValue(700)
                window.ephemeris_row_limit.setValue(250)
            finally:
                window.close()
            reopened = NEOMapperMainWindow()
            try:
                self.assertEqual(reopened.animation_frame_limit.value(), 700)
                self.assertEqual(reopened.ephemeris_row_limit.value(), 250)
            finally:
                reopened.close()

    def test_ephemeris_dialog_opens_with_local_and_utc_defaults(self) -> None:
        from datetime import datetime, timezone
        from neomapper.shared.utils import timezone_from_reference

        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.ref_lat_edit.setText("-19.9")
                window.ref_lon_edit.setText("-43.9")
                for mode in ("LOCAL", "UTC"):
                    window.time_mode_combo.setCurrentText(mode)
                    zone = timezone.utc if mode == "UTC" else timezone_from_reference(-19.9, -43.9)[1]
                    expected = datetime.now(zone).replace(tzinfo=None)

                    def inspect_dialog(dialog):
                        dates = dialog.findChildren(gui.QDateTimeEdit)
                        start = dates[0].dateTime().toPython()
                        self.assertLess(abs((start - expected).total_seconds()), 10)
                        self.assertEqual(dates[0].dateTime().secsTo(dates[1].dateTime()), 3600)
                        return 0

                    with patch.object(gui.QDialog, "exec", inspect_dialog):
                        window.open_ephemeris_dialog()
            finally:
                window.close()

    def test_ephemeris_save_passes_worker_progress_argument(self) -> None:
        from PySide6.QtWidgets import QPushButton

        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.object_edit.setText("220P")
                window.language_header_combo.setCurrentText("EN")

                def click_save(dialog):
                    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Save PDF")
                    button.click()
                    return 0

                with patch.object(gui.QDialog, "exec", click_save), patch.object(
                    window, "_run_responsive", side_effect=lambda fn: fn(lambda *_: None)
                ), patch.object(gui, "query_report_ephemerides", return_value=[]) as query, patch.object(
                    gui.QFileDialog, "getSaveFileName", return_value=(str(Path(folder) / "test.pdf"), "PDF")
                ), patch.object(gui, "create_ephemeris_pdf") as report, patch.object(gui.QMessageBox, "critical") as error:
                    window.open_ephemeris_dialog()
                    error.assert_not_called()
                    query.assert_called_once()
                    report.assert_called_once()
            finally:
                window.close()

    def test_ephemeris_preview_queries_once_and_cleans_temporary_pdf(self) -> None:
        from PySide6.QtWidgets import QPushButton
        from reportlab.pdfgen.canvas import Canvas
        from neomapper.presentation.report_preview import ReportPreviewDialog

        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            paths: list[Path] = []

            def create_report(_object: str, _rows: list, path: str, _language: str) -> None:
                pdf = Canvas(path)
                pdf.drawString(72, 720, "Preview")
                pdf.save()
                paths.append(Path(path))

            def inspect_dialog(dialog: gui.QDialog) -> int:
                if isinstance(dialog, ReportPreviewDialog):
                    self.assertEqual(dialog.document.pageCount(), 1)
                    self.assertTrue(paths[0].exists())
                else:
                    next(b for b in dialog.findChildren(QPushButton) if b.text() == "View report").click()
                return 0

            try:
                window.language_header_combo.setCurrentText("EN")
                with patch.object(gui.QDialog, "exec", inspect_dialog), patch.object(
                    window, "_run_responsive", side_effect=lambda fn: fn(lambda *_: None)
                ), patch.object(gui, "query_report_ephemerides", return_value=[]) as query, patch.object(
                    gui, "create_ephemeris_pdf", side_effect=create_report
                ), patch.object(gui.QFileDialog, "getSaveFileName") as save, patch.object(gui.QMessageBox, "critical") as error:
                    window.open_ephemeris_dialog()
                    error.assert_not_called()
                    query.assert_called_once()
                    save.assert_not_called()
                    self.assertEqual(len(paths), 1)
                    self.assertFalse(paths[0].exists())
            finally:
                window.close()

    def test_map_uses_layer_date_time_and_selected_object(self) -> None:
        from PySide6.QtCore import QDate, QTime
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.object_edit.setText("220P")
                original = window.datetime_edit.dateTime()
                window.map_date_edit.setDate(QDate(2029, 4, 13))
                window.map_time_edit.setTime(QTime(22, 15, 30))
                for mode in ("UTC", "LOCAL"):
                    window.time_mode_combo.setCurrentText(mode)
                    for index, name in ((0, "build_visibility_figure"), (1, "build_sky_figure")):
                        window.map_type_combo.setCurrentIndex(index)
                        with patch.object(window, "_run_responsive", side_effect=lambda fn: fn(None)), patch.object(
                            gui, name, return_value=(None, {"targetname": "220P", "geo_km": 1234})
                        ) as build, patch("astroquery.jplhorizons.Horizons", side_effect=RuntimeError("offline")), patch(
                            "neomapper.presentation.gui.QMessageBox.critical"
                        ) as error:
                            window.generate_map()
                            self.assertEqual(build.call_args.args, ("220P", "2029-04-13 22:15:30"))
                            self.assertEqual(build.call_args.kwargs["time_mode"], mode)
                            self.assertIn("20290413_221530", build.call_args.kwargs["output_png"])
                            self.assertEqual(Path(build.call_args.kwargs["output_png"]).parent, gui.object_output_dir("220P"))
                            self.assertEqual(window.datetime_edit.dateTime(), original)
                            error.assert_not_called()
                layout = window.map_date_edit.parentWidget().layout()
                self.assertLess(layout.indexOf(window.map_date_edit), layout.indexOf(window.map_type_combo))
                window.datetime_edit.setDate(QDate(2030, 1, 2))
                self.assertEqual(window.map_date_edit.date(), QDate(2030, 1, 2))
            finally:
                window.close()

    def test_distance_preference_updates_cards_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.language_header_combo.setCurrentText("PT")
                window.last_result = {"geo_km": 149597870.7, "heliocentric_distance_au": 2.0}
                window.distance_unit_combo.setCurrentText("UA")
                self.assertEqual(window.object_earth_distance.text(), "1,000000 UA")
                self.assertEqual(window.object_sun_distance.text(), "2,000000 UA")
                window.distance_unit_combo.setCurrentText("km")
                self.assertEqual(window.object_earth_distance.text(), "149.597.871 km")
                window.distance_unit_combo.setCurrentText("UA")
                self.assertEqual(gui.load_config()["ui"]["distance_unit"], "UA")
                window.language_header_combo.setCurrentText("EN")
                self.assertEqual(window.object_earth_distance.text(), "1.000000 AU")
            finally:
                window.close()
            reopened = NEOMapperMainWindow()
            try:
                self.assertEqual(reopened.distance_unit_combo.currentText(), "UA")
            finally:
                reopened.close()

    def test_distance_change_refreshes_static_preview_and_clears_old_animation(self) -> None:
        from neomapper.presentation.mapplot import build_solar_system_sketch
        from matplotlib import pyplot as plt
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            path = Path(folder) / "solar.png"
            figure = build_solar_system_sketch("Fixture", 1., str(path), obstime="2026-09-08", distance_unit="km", language="PT")
            try:
                window._distance_preview = (figure, path)
                window.show_png(path)
                window.distance_unit_combo.setCurrentText("UA")
                self.assertIn("1,000000 UA", figure.axes[0].get_title())
                self.assertFalse(window.preview_label.pixmap().isNull())
                window.set_player_frames([path])
                window.distance_unit_combo.setCurrentText("km")
                self.assertEqual(window.player_frames, [])
                self.assertTrue(window.preview_label.pixmap().isNull())
                self.assertTrue(path.exists())
            finally:
                plt.close(figure)
                window.close()

    def test_missing_object_message_follows_selected_language(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                for language, title, phrase in [
                    ("PT", "Objeto não encontrado", "nas bases de dados do JPL ou MPC"),
                    ("ES", "Objeto no encontrado", "en las bases de datos del JPL o MPC"),
                    ("EN", "Object not found", "in the JPL or MPC databases"),
                ]:
                    window.language_header_combo.setCurrentText(language)
                    with patch.object(window, "_run_responsive", side_effect=gui.ObjectNotFoundError("technical provider details")), patch(
                        "neomapper.presentation.gui.QMessageBox.warning"
                    ) as warning, patch("neomapper.presentation.gui.QMessageBox.critical") as critical:
                        window.object_search_btn.click()
                        self.assertEqual(warning.call_args.args[1], title)
                        self.assertIn(phrase, warning.call_args.args[2])
                        self.assertNotIn("technical provider details", warning.call_args.args[2])
                        self.assertIn("technical provider details", (gui.logs_dir() / "gui_error.log").read_text(encoding="utf-8"))
                        self.assertTrue(window.object_search_btn.isEnabled())
                        self.assertFalse(window.plot_solar_btn.isEnabled())
                        critical.assert_not_called()
            finally:
                window.close()

    def test_animation_preserves_requested_times_after_utc_or_clipped_result(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.map_type_combo.setCurrentIndex(1)
                requested_start = window.anim_start_edit.dateTime()
                requested_end = window.anim_end_edit.dateTime()
                for mode in ("LOCAL", "UTC"):
                    window.time_mode_combo.setCurrentText(mode)
                    for effective_start in ("2029-04-13 21:00:00", "2029-04-13 22:30:00"):
                        with patch.object(window, "_run_responsive", side_effect=lambda fn, _progress: fn(lambda _: None)), patch(
                            "neomapper.presentation.gui.generate_animation", return_value={
                                "outputs": [], "frames_dir": folder,
                                "effective_start_time": effective_start,
                                "effective_end_time": "2029-04-14 01:00:00",
                            },
                        ) as generate, patch("neomapper.presentation.gui.QMessageBox.critical") as error:
                            window.generate_animation_output()
                            self.assertEqual(generate.call_args.kwargs["max_frames"], 500)
                            self.assertEqual(Path(generate.call_args.kwargs["base_output"]).parent, gui.object_output_dir(window.object_edit.text()))
                            self.assertEqual(generate.call_args.kwargs["start_time"], requested_start.toString("yyyy-MM-dd HH:mm:ss"))
                            self.assertEqual(generate.call_args.kwargs["end_time"], requested_end.toString("yyyy-MM-dd HH:mm:ss"))
                            self.assertEqual(generate.call_args.kwargs["time_mode"], mode)
                            self.assertEqual(window.anim_start_edit.dateTime(), requested_start)
                            self.assertEqual(window.anim_end_edit.dateTime(), requested_end)
                            error.assert_not_called()
            finally:
                window.close()

    def test_initial_object_workflow_and_failed_search(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                self.assertTrue(window.tab_buttons[0].isChecked())
                self.assertTrue(all(not b.isChecked() for b in window.tab_buttons[1:]))
                self.assertTrue(window.object_search_btn.isEnabled())
                self.assertEqual(window.object_search_btn.objectName(), "Blue")
                self.assertFalse(window.plot_solar_btn.isEnabled())
                self.assertFalse(window.object_next_btn.isEnabled())
                with patch.object(window, "_run_responsive", side_effect=RuntimeError("offline")), patch(
                    "neomapper.presentation.gui.QMessageBox.critical",
                ):
                    window.object_search_btn.click()
                self.assertTrue(window.object_search_btn.isEnabled())
                self.assertFalse(window.plot_solar_btn.isEnabled())
                self.assertFalse(window.object_next_btn.isEnabled())
            finally:
                window.close()

    def test_map_controls_follow_type_in_all_languages(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                for language in ("PT", "ES", "EN"):
                    window.language_header_combo.setCurrentText(language)
                    for index in (1, 0, 1):
                        window.map_type_combo.setCurrentIndex(index)
                        self.assertEqual(window.star_magnitude_combo.isHidden(), index == 0)
                        self.assertEqual(window.tr_widgets["Star magnitude limit"].isHidden(), index == 0)
                        for control in window.visibility_map_controls:
                            self.assertEqual(control.isHidden(), index == 1)
                        self.assertFalse(window.generate_btn.isHidden())
                        self.assertFalse(window.layers_next_btn.isHidden())
                window.language_header_combo.setCurrentText("PT")
                self.assertEqual(window.layers_next_btn.text(), "Continuar para Animação →")
                for _ in range(2):
                    window._continue_to_layers()
                    window.layers_next_btn.click()
                    self.assertEqual(window.right_stack.currentIndex(), 4)
                    self.assertTrue(window.tab_buttons[3].isEnabled())
                    self.assertTrue(window.tab_buttons[3].isChecked())
            finally:
                window.close()

    def test_generate_button_displays_both_map_types_and_search_shows_hint(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            window.distance_unit_combo.setCurrentText("UA")
            def render(_object: str, _time: str, **kwargs):
                png = QImage(200, 100, QImage.Format_RGB32)
                png.fill(0x123456)
                png.save(kwargs["output_png"])
                self.assertEqual(kwargs["distance_unit"], "UA")
                return None, {"targetname": "Fixture", "geo_km": 1234}
            try:
                window.language_header_combo.setCurrentText("PT")
                with patch.object(window, "_run_responsive", side_effect=lambda fn: fn(None)), patch(
                    "neomapper.presentation.gui.build_visibility_figure", side_effect=render,
                ) as visibility, patch(
                    "neomapper.presentation.gui.build_sky_figure", side_effect=render,
                ) as sky, patch("astroquery.jplhorizons.Horizons", side_effect=RuntimeError("offline")), patch(
                    "neomapper.presentation.gui.QMessageBox.critical",
                ) as error:
                    for index, builder in ((0, visibility), (1, sky)):
                        window.map_type_combo.setCurrentIndex(index)
                        window.generate_btn.click()
                        builder.assert_called_once()
                        self.assertFalse(window.preview_label.pixmap().isNull())
                        self.assertTrue(window.last_png.is_file())
                        self.assertTrue(window.moon_curve_btn.isHidden())
                    window.object_search_btn.click()
                    self.assertEqual(window.preview_label.text(), "Clique em Plotar Sistema Solar para ver a posição do objeto em relação aos planetas.")
                    self.assertTrue(window.plot_solar_btn.isEnabled())
                    self.assertTrue(window.object_next_btn.isEnabled())
                    window.object_next_btn.click()
                    self.assertEqual(window.right_stack.currentIndex(), 0)
                    self.assertIn("durante a noite", window.preview_label.text())
                    window.object_edit.setText("new object")
                    self.assertFalse(window.plot_solar_btn.isEnabled())
                    self.assertFalse(window.object_next_btn.isEnabled())
                    self.assertIsNone(window.last_png)
                    error.assert_not_called()
            finally:
                window.close()

    def test_observation_controls_move_to_layers_and_moon_toggle_uses_cached_images(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.language_header_combo.setCurrentText("PT")
                layers = window.right_stack.widget(3)
                self.assertTrue(layers.isAncestorOf(window.cb_obs_box))
                self.assertTrue(layers.isAncestorOf(window.obs_box_pos_combo))
                self.assertTrue(window.summary_time.isHidden())
                self.assertTrue(window.summary_dist.isHidden())
                plain, moon = Path(folder) / "plain.png", Path(folder) / "moon.png"
                window._altitude_chart_paths = (plain, moon)
                with patch.object(window, "show_png") as show:
                    window.moon_curve_btn.click()
                    show.assert_called_with(moon)
                    self.assertEqual(window.moon_curve_btn.text(), "Ocultar Lua")
                    window.moon_curve_btn.click()
                    show.assert_called_with(plain)
                    self.assertEqual(window.moon_curve_btn.text(), "Mostrar Lua")
            finally:
                window.close()

    def test_observation_buttons_translate_and_always_advance_to_layers(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": folder}):
            window = NEOMapperMainWindow()
            try:
                window.language_header_combo.setCurrentText("PT")
                self.assertEqual(window.plot_altitude_btn.text(), "Plotar gráfico de altitude")
                self.assertEqual(window.obs_next_btn.text(), "Continuar para Camadas →")
                for step in (1, 3):
                    window.workflow_step = step
                    window.right_stack.setCurrentIndex(0)
                    window.obs_next_btn.click()
                    self.assertEqual(window.right_stack.currentIndex(), 3)
                    self.assertTrue(window.tab_buttons[2].isChecked())
                    self.assertTrue(window.tab_buttons[2].isEnabled())
            finally:
                window.close()

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_window_builds_with_versioned_title(self):
        runtime = Path(__file__).resolve().parents[2] / "var" / "test-ui"
        runtime.mkdir(parents=True, exist_ok=True)
        with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(runtime)}):
            window = NEOMapperMainWindow()
            try:
                self.assertIn("NEOMapper", window.windowTitle())
                self.assertFalse(window.windowIcon().isNull())
                self.assertGreater(window.minimumWidth(), 0)
                self.assertGreater(window.minimumHeight(), 0)
            finally:
                window.close()

    def test_runtime_path_type_is_available_to_animation_handlers(self):
        self.assertIs(gui.Path, Path)

    def test_application_icon_is_a_packaged_windows_icon(self):
        icon_path = application_icon_path()
        self.assertTrue(icon_path.is_file())
        self.assertEqual(icon_path.suffix, ".ico")

    def test_expensive_work_runs_outside_gui_thread(self):
        runtime = Path(__file__).resolve().parents[2] / "var" / "test-ui-worker"
        with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(runtime)}):
            window = NEOMapperMainWindow()
            try:
                gui_thread = threading.get_ident()
                worker_thread = window._run_responsive(lambda _emit: threading.get_ident())
                self.assertNotEqual(worker_thread, gui_thread)
            finally:
                window.close()

    def test_player_runs_with_session_only_animation_frames(self):
        runtime = Path(__file__).resolve().parents[2] / "var" / "test-ui-player"
        with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(runtime)}):
            window = NEOMapperMainWindow()
            try:
                with tempfile.TemporaryDirectory() as temporary_directory:
                    frame = Path(temporary_directory) / "frame_0000.png"
                    frame.touch()
                    window.set_player_frames([frame])

                    self.assertTrue(window.player_play_btn.isEnabled())
                    window.toggle_player()
                    self.assertTrue(window.player_timer.isActive())
                    self.assertEqual(window.player_play_btn.text(), "Pause")
            finally:
                window.close()

    def test_reusing_animation_output_directory_keeps_new_frames(self):
        runtime = Path(__file__).resolve().parents[2] / "var" / "test-ui-player-reuse"
        with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(runtime)}):
            window = NEOMapperMainWindow()
            try:
                with tempfile.TemporaryDirectory() as temporary_directory:
                    frames_dir = Path(temporary_directory) / "same_animation_frames"
                    frames_dir.mkdir()
                    frame = frames_dir / "frame_0000.png"
                    frame.touch()
                    window._transient_frames_dir = frames_dir

                    window.set_player_frames([frame])

                    self.assertTrue(frame.exists())
                    self.assertEqual(window.player_frames, [frame])
            finally:
                window.close()
