import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from dataclasses import replace
from astropy.time import Time
from PySide6.QtWidgets import QApplication
from neomapper.domain.object_summary import ObjectSummary, SummaryTarget, SummarySample
from neomapper.presentation.object_summary import ObjectSummaryWidget
from unittest.mock import patch
from PySide6.QtGui import QImage
from neomapper.presentation import gui
from neomapper.domain.observing import observing_window_from_samples


def test_compact_summary_keeps_closest_approach_visible_when_resized() -> None:
    from PySide6.QtWidgets import QHeaderView
    app = QApplication.instance() or QApplication([])
    t = Time("2026-09-10", scale="utc")
    row = SummarySample(t, 1., 1., 51., 8., 12., "T", 100., 20., 260.)
    data = ObjectSummary(SummaryTarget("1P/Halley", "1", True, t), row, row, row, t, t)
    widget = ObjectSummaryWidget()
    widget.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    try:
        widget.set_summary(data, "UTC", 0, 0)
        widget.show()
        for width in (640, 1100, 760):
            for language in ("PT", "ES", "EN"):
                widget.set_language(language)
                widget.resize(width, 400)
                app.processEvents()
                rect = widget.table.visualItemRect(widget.table.item(2, 0))
                assert widget.table.viewport().rect().contains(rect)
                assert widget.table.verticalScrollBar().maximum() == 0
    finally:
        widget.close()


def test_extended_summary_labels_help_and_export_follow_language() -> None:
    app = QApplication.instance() or QApplication([])
    t = Time("2061-07-28", scale="utc")
    row = SummarySample(t, .6, .48, 51., 8., None, "T", 100., 20., 260.)
    data = ObjectSummary(SummaryTarget("1P/Halley", "1", True, t, 27567.), row, row, row, t, t, True, True)
    widget = ObjectSummaryWidget()
    try:
        for lang, expected in (("PT", "Próximo periélio"), ("ES", "Próximo perihelio"), ("EN", "Next perihelion")):
            widget.set_language(lang)
            widget.set_summary(data, "UTC", 0, 0)
            assert widget.table.item(0, 0).text() == expected
            assert len(widget.table.item(0, 0).toolTip()) > len(expected)
            assert "2061-07-28" in widget.note.text()
            assert widget.report().rows[0][0] == expected
        widget.set_summary(replace(data, perihelion_refined=False, search_limited=True), "UTC", 0, 0)
        assert widget.table.item(0, 0).text() == "Estimated perihelion"
        assert "not confirmed" in widget.note.text()
    finally:
        widget.close()


def test_pa_column_only_for_comets_and_local_date_rollover() -> None:
    app = QApplication.instance() or QApplication([])
    t = Time("2026-09-10T01:00:00", scale="utc")
    row = SummarySample(t, 1.769, 1.09, 51.5, 8.25, 11.3, "T", 115., 31.1, 260.)
    data = ObjectSummary(SummaryTarget("220P/McNaught", "1", True, t), row, row, row, t, t)
    widget = ObjectSummaryWidget()
    try:
        widget.set_language("PT")
        widget.set_summary(data, "LOCAL", -19.9, -43.9)
        assert not widget.table.isColumnHidden(9)
        assert widget.table.item(1, 1).text() == "2026-09-09"
        assert widget.table.item(1, 9).text() == "260,0°"
        assert "03h 26m" in widget.table.item(1, 5).text()
        assert widget.table.item(1, 0).text() == "Data selecionada"
        assert widget.table.item(1, 3).text() == "264.638.633 km"
        assert widget.table.item(1, 4).text() == "163.061.679 km"
        widget.set_distance_unit("UA")
        assert widget.table.item(1, 3).text() == "1,769000 UA"
        assert widget.table.item(1, 4).text() == "1,090000 UA"
        widget.set_summary(replace(data, target=replace(data.target, is_comet=False)), "UTC", 0, 0)
        assert widget.table.isColumnHidden(9)
        widget.reset()
        assert widget.table.isHidden()
    finally:
        widget.close()


def test_summary_is_below_plot_in_projection_and_failure_keeps_chart(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    t = Time("2026-09-09", scale="utc")
    row = SummarySample(t, 1., 1., 51., 8., None, "V", 100., 20., None)
    data = ObjectSummary(SummaryTarget("Fixture", "1", False, t), row, row, row, t, t)
    with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(tmp_path)}):
        window = gui.NEOMapperMainWindow()
        window.right_stack.setCurrentIndex(0)
        try:
            assert window.orbital_summary_btn.isEnabled()
            def chart(*args, **kwargs):
                image = QImage(40, 40, QImage.Format_RGB32)
                image.fill(0)
                image.save(str(args[5]))
                image.save(str(kwargs["moon_output_png"]))
                return args[5]
            with patch.object(window, "_run_responsive", side_effect=lambda fn: fn(None)), patch.object(gui, "build_altitude_chart", side_effect=chart), patch.object(gui, "calculate_object_summary", return_value=data) as calculate:
                window.plot_altitude_chart()
                calculate.assert_not_called()
                assert window.orbital_summary.data is None
                assert window.orbital_summary_btn.isEnabled()
                with patch.object(gui.QDialog, "exec", return_value=0) as expanded:
                    window.orbital_summary_btn.click()
                    expanded.assert_not_called()
                calculate.assert_called_once()
                assert window.orbital_summary.data == data
                assert window.orbital_summary_btn.isEnabled()
                assert window.orbital_summary_btn.objectName() == "Blue"
                assert not window.orbital_summary.expand.isHidden()
                window.distance_unit_combo.setCurrentText("UA")
                assert window.orbital_summary.table.item(1, 3).text().endswith((" AU", " UA"))
                window.distance_unit_combo.setCurrentText("km")
                assert window.orbital_summary.table.item(1, 3).text().endswith(" km")
                assert window.map_area.isAncestorOf(window.orbital_summary)
                assert window.map_area.isAncestorOf(window.moon_curve_btn)
                assert not window.right_stack.isAncestorOf(window.orbital_summary)
                assert window.map_area.layout().indexOf(window.plot_area) < window.map_area.layout().indexOf(window.altitude_details)
                assert not window.altitude_details.isHidden()
                window._activate_workflow_page(3)
                assert window.altitude_details.isHidden()
                window._activate_workflow_page(0)
                assert not window.altitude_details.isHidden()
                assert window.orbital_summary.data == data
            with patch.object(window, "_run_responsive", side_effect=lambda fn: fn(None)), patch.object(gui, "build_altitude_chart", side_effect=chart), patch.object(gui, "calculate_object_summary", side_effect=RuntimeError("offline")):
                window.plot_altitude_chart()
                assert window.orbital_summary.data == data
                assert window.orbital_summary_btn.isEnabled()
                window.orbital_summary_btn.click()
                assert window.orbital_summary.data is None
                assert window.orbital_summary_btn.isEnabled()
                assert not window.preview_label.pixmap().isNull()
                assert window.plot_altitude_btn.isEnabled()
                window.ref_lat_edit.setText("10")
                assert window.orbital_summary_btn.isEnabled()
                with patch.object(gui.QMessageBox, "critical"), patch.object(gui, "build_altitude_chart", side_effect=RuntimeError("offline")):
                    window.plot_altitude_chart()
                assert window.orbital_summary_btn.isEnabled()
        finally:
            window.close()


def test_summary_without_altitude_plot_and_expansion_only_on_request(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    t = Time("2026-09-09T21:42:00", scale="utc")
    row = SummarySample(t, 1., 1., 51., 8., None, "V", 100., 20., None)
    data = ObjectSummary(SummaryTarget("Fixture", "1", False, t), row, row, row, t, t)
    with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(tmp_path)}):
        window = gui.NEOMapperMainWindow()
        try:
            window._activate_workflow_page(0)
            window.time_mode_combo.setCurrentText("LOCAL")
            window.datetime_edit.setDateTime(gui.QDateTime(2026, 9, 9, 0, 0, 0))
            window.map_time_edit.setTime(gui.QDateTime(2026, 9, 9, 18, 42, 0).time())
            assert window.orbital_summary_btn.isEnabled()
            def run_summary(fn):
                assert window.orbital_summary.calculating
                assert not window.orbital_summary.loading.isHidden()
                assert not window.altitude_details.isHidden()
                assert window.orbital_summary.loading.text() == window.translator.tr("Calculating orbital summary…")
                return fn(None)
            with patch.object(window, "_run_responsive", side_effect=run_summary), patch.object(gui, "build_altitude_chart") as chart, patch.object(gui, "calculate_object_summary", return_value=data) as calculate, patch.object(gui.QDialog, "exec", return_value=0) as expanded:
                window.orbital_summary_btn.click()
                chart.assert_not_called()
                calculate.assert_called_once()
                assert calculate.call_args.args[1].utc.isot == t.utc.isot
                expanded.assert_not_called()
                assert window.orbital_summary.data == data
                assert window.orbital_summary.loading.isHidden()
                assert not window.orbital_summary.calculating
                assert not window.altitude_details.isHidden()
                assert not window.orbital_summary.expand.isHidden()
                window.orbital_summary.expand.click()
                expanded.assert_called_once()
                window._activate_workflow_page(3)
                window._activate_workflow_page(0)
                assert not window.altitude_details.isHidden()
                window.object_edit.setText("")
                assert window.orbital_summary_btn.isEnabled()
                window.orbital_summary_btn.click()
                calculate.assert_called_once()
                assert window.orbital_summary_btn.isEnabled()
        finally:
            window.close()


def test_plot_uses_layer_instant_and_refreshes_panel_from_same_samples(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    best_time = Time("2026-09-10T00:25:00", scale="utc")
    obs = observing_window_from_samples([(0, best_time, 89.7, 180., -50.)], 0, -12)
    with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(tmp_path)}):
        window = gui.NEOMapperMainWindow()
        try:
            window.right_stack.setCurrentIndex(0)
            window.time_mode_combo.setCurrentText("LOCAL")
            window.datetime_edit.setDateTime(gui.QDateTime(2026, 9, 9, 0, 0, 0))
            window.map_time_edit.setTime(gui.QDateTime(2026, 9, 9, 18, 42, 0).time())
            def chart(*args, **kwargs):
                assert args[1].utc.isot == "2026-09-09T21:42:00.000"
                assert kwargs["sun_limit_deg"] == -12
                image = QImage(40, 40, QImage.Format_RGB32); image.fill(0)
                image.save(str(args[5])); image.save(str(kwargs["moon_output_png"]))
                return gui.AltitudeChartResult(args[5], obs)
            with patch.object(window, "_run_responsive", side_effect=lambda fn: fn(None)), patch.object(gui, "build_altitude_chart", side_effect=chart), patch.object(gui, "calculate_object_summary", side_effect=RuntimeError("offline")):
                window.plot_altitude_chart()
            assert "89.7° @ 21:25 LOCAL" == window.summary_alt.text()
            assert "21:25 LOCAL" in window.window_best_label.text()
            assert "2026-09-09" in window.window_best_label.toolTip()
            window.summary_alt.setText("stale")
            window._activate_workflow_page(3)
            window._activate_workflow_page(0)
            assert "89.7° @ 21:25 LOCAL" == window.summary_alt.text()
        finally:
            window.close()
