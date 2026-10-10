import math
import logging

from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import (QDialog, QFormLayout, QSpinBox, QCheckBox,
                              QDialogButtonBox, QVBoxLayout)
from krita import Krita, Extension

from pynavlib import pynavlib_interface as pynav

log = logging.getLogger("spacemouse_krita")

ZERO_M = [
    [1., 0., 0., 0.],
    [0., 1., 0., 0.],
    [0., 0., 1., 0.],
    [0., 0., 0., 1.]
]
FIXED_HALF = 500.0
CFG_GROUP = "spacemouse_krita"

# 归一化尺度：让不同物理轴输入变成大约 -1 到 +1 的范围
RAW_DX_SCALE  = 40.0    # 左右推满力时的 dx 量级
RAW_DY_SCALE  = 25.0    # 上下推满力时的 dy 量级
RAW_DEV_SCALE = 500.0   # 前后推满力时的 deviation 量级
RAW_YAW_SCALE = 3.0     # 拧动满力时的 yaw 量级

DEFAULTS = {
    "pan_x_gain":  "100",     # 平移X乘数
    "pan_y_gain":  "100",     # 平移Y乘数
    "zoom_gain":   "100",      # 缩放乘数（百分比/帧）
    "rot_gain":    "5",      # 旋转乘数（度/帧）
    "swap_yz":     "true",
}


def yaw_of(m):
    return math.degrees(math.atan2(m[0][2], m[0][0]))

def get_canvas():
    w = Krita.instance().activeWindow()
    return w.activeView().canvas() if w and w.activeView() else None

def get_doc():
    return Krita.instance().activeDocument()


def load_config():
    inst = Krita.instance()
    return {k: inst.readSetting(CFG_GROUP, k, v) for k, v in DEFAULTS.items()}

def save_config(cfg):
    inst = Krita.instance()
    for k, v in cfg.items():
        inst.writeSetting(CFG_GROUP, k, v)


# ---------- Navlib 模型 ----------

class NavlibModel(pynav.NavlibNavigationModel):
    def __init__(self, cfg):
        super().__init__(multi_threaded=False, navlib_options=6, verbose_mode=False)
        self.cfg = cfg

    def _pan_x_gain(self): return float(self.cfg.get("pan_x_gain", "50"))
    def _pan_y_gain(self): return float(self.cfg.get("pan_y_gain", "50"))
    def _zoom_gain(self):  return float(self.cfg.get("zoom_gain",  "5"))
    def _rot_gain(self):   return float(self.cfg.get("rot_gain",   "5"))
    def _swap(self):       return self.cfg.get("swap_yz", "false") == "true"

    # -------- Getter --------
    def get_coordinate_system(self): return pynav.NavlibMatrix()
    def get_front_view(self):        return pynav.NavlibMatrix()
    def get_camera_matrix(self):     return pynav.NavlibMatrix([list(r) for r in ZERO_M])
    def get_camera_target(self):     return pynav.NavlibVector(0., 0., 0.)
    def is_user_pivot(self):         return True
    def get_pivot_position(self):    return pynav.NavlibVector(0., 0., 0.)
    def get_view_extents(self):
        return pynav.NavlibBox(
            pynav.NavlibVector(-FIXED_HALF, -FIXED_HALF, -1.),
            pynav.NavlibVector( FIXED_HALF,  FIXED_HALF,  1.))
    def get_view_focus_distance(self): return 2048.0
    def get_view_construction_plane(self): return None
    def get_view_fov(self):          return 0.785398
    def get_is_view_perspective(self): return False
    def get_is_view_rotatable(self): return True
    def get_pointer_position(self):  return pynav.NavlibVector(0,0,0)
    def get_model_extents(self):
        d = get_doc()
        if not d:
            return pynav.NavlibBox(pynav.NavlibVector(0,0,0), pynav.NavlibVector(0,0,0))
        return pynav.NavlibBox(pynav.NavlibVector(0,0,0),
                                pynav.NavlibVector(d.width(), d.height(), 0))
    def get_is_selection_empty(self): return True
    def get_selection_extents(self):
        return pynav.NavlibBox(pynav.NavlibVector(0,0,0), pynav.NavlibVector(0,0,0))
    def get_selection_transform(self): return pynav.NavlibMatrix()
    def get_units_to_meters(self):   return 1.0/96.0*0.0254
    def get_floor_plane(self):       return None
    def get_pivot_visible(self):     return False
    def get_hit_look_at(self):       return pynav.NavlibVector(0,0,0)

    def set_motion_flag(self, f): pass

    # -------- 主处理：dx / dy / yaw --------
    def set_camera_matrix(self, matrix):
        m = matrix._matrix
        dx, dy = m[0][3], m[1][3]
        yaw = yaw_of(m)

        canvas = get_canvas()
        if not canvas:
            return

        swap = self._swap()

        # 归一化
        nx   = dx  / RAW_DX_SCALE
        ny   = dy  / RAW_DY_SCALE
        nrot = yaw / RAW_YAW_SCALE

        # --- 左右推 → 水平平移 ---
        pan_x = int(nx * self._pan_x_gain())
        if pan_x != 0:
            try: canvas.pan(QPoint(pan_x, 0))
            except Exception: pass

        # --- 上下推：默认→缩放；交换后→垂直平移 ---
        if abs(dy) > 0.01:
            if swap:
                pan_y = int(ny * self._pan_y_gain())
                if pan_y != 0:
                    try: canvas.pan(QPoint(0, -pan_y))
                    except Exception: pass
            else:
                z = canvas.zoomLevel() or 1.0
                new_z = z * (1.0 + ny * self._zoom_gain() / 100.0)
                if 0.05 < new_z < 30.0:
                    try: canvas.setZoomLevel(new_z)
                    except Exception: pass

        # --- 拧动 → 旋转 ---
        if abs(yaw) > 0.001:
            try:
                canvas.setRotation(canvas.rotation() + nrot * self._rot_gain())
            except Exception: pass

        canvas.update()

    # -------- 前后推：默认→垂直平移；交换后→缩放 --------
    def set_view_extents(self, e):
        w = e._max._x - e._min._x
        deviation = w - 2.0 * FIXED_HALF
        if abs(deviation) < 0.01:
            return

        canvas = get_canvas()
        if not canvas:
            return

        swap = self._swap()
        nz = deviation / RAW_DEV_SCALE

        if swap:
            z = canvas.zoomLevel() or 1.0
            new_z = z * (1.0 + nz * self._zoom_gain() / 100.0)
            if 0.05 < new_z < 30.0:
                try: canvas.setZoomLevel(new_z)
                except Exception: pass
        else:
            pan_y = int(nz * self._pan_y_gain())
            if pan_y != 0:
                try: canvas.pan(QPoint(0, pan_y))
                except Exception: pass

        canvas.update()

    def set_transaction(self, t): pass
    def set_camera_target(self, *a): pass
    def set_pivot_position(self, *a): pass
    def set_pivot_visible(self, *a): pass
    def set_pointer_position(self, *a): pass
    def set_selection_transform(self, *a): pass
    def set_view_fov(self, *a): pass
    def set_view_frustum(self, *a): pass
    def set_hit_aperture(self, *a): pass
    def set_hit_direction(self, *a): pass
    def set_hit_look_from(self, *a): pass
    def set_hit_selection_only(self, *a): pass
    def set_active_command(self, *a): pass
    def set_settings_changed(self, *a): pass
    def set_key_press(self, *a): pass
    def set_key_release(self, *a): pass


# ---------- 设置对话框 ----------

class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SpaceMouse 设置")
        self.cfg = dict(cfg)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        def make_spin(key, label):
            sp = QSpinBox()
            sp.setRange(1, 999999)
            sp.setValue(int(self.cfg.get(key, DEFAULTS[key])))
            form.addRow(label, sp)
            return sp

        self.pan_x_spin = make_spin("pan_x_gain", "平移速度 X 乘数：")
        self.pan_y_spin = make_spin("pan_y_gain", "平移速度 Y 乘数：")
        self.zoom_spin  = make_spin("zoom_gain",  "缩放速度乘数：")
        self.rot_spin   = make_spin("rot_gain",   "旋转速度乘数：")

        self.swap_chk = QCheckBox("交换 上下推↔前后推 的功能")
        self.swap_chk.setChecked(self.cfg.get("swap_yz", "false") == "true")
        form.addRow("", self.swap_chk)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config(self):
        self.cfg["pan_x_gain"] = str(self.pan_x_spin.value())
        self.cfg["pan_y_gain"] = str(self.pan_y_spin.value())
        self.cfg["zoom_gain"]  = str(self.zoom_spin.value())
        self.cfg["rot_gain"]   = str(self.rot_spin.value())
        self.cfg["swap_yz"]    = "true" if self.swap_chk.isChecked() else "false"
        return self.cfg


# ---------- Extension 主类 ----------

class SpaceMouseExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.model = None

    def setup(self):
        pass

    def createActions(self, window):
        act_toggle = window.createAction(
            "spacemouse_toggle", "启用/停止 SpaceMouse", "tools/scripts")
        act_toggle.triggered.connect(self._toggle)

        act_settings = window.createAction(
            "spacemouse_settings", "SpaceMouse 设置...", "tools/scripts")
        act_settings.triggered.connect(self._open_settings)

    def _toggle(self):
        if self.model is None:
            self._start()
        else:
            self._stop()

    def _start(self):
        try:
            cfg = load_config()
            self.model = NavlibModel(cfg)
            self.model.put_profile_hint("Krita")
            self.model.enable_navigation(True)
            log.info("SpaceMouse 已启用")
        except Exception as e:
            log.exception(f"启动失败: {e}")
            self.model = None

    def _stop(self):
        try:
            if self.model is not None:
                self.model.enable_navigation(False)
                self.model = None
                log.info("SpaceMouse 已停止")
        except Exception as e:
            log.exception(f"停止失败: {e}")

    def _open_settings(self):
        was_running = self.model is not None
        dlg = SettingsDialog(load_config())
        if dlg.exec_() != QDialog.Accepted:
            return
        save_config(dlg.get_config())
        # 若之前已启用，自动重启让新设置生效
        if was_running:
            self._stop()
            self._start()