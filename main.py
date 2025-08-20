import os, sys, time
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QFrame, QPushButton, QSlider, QLabel, QWidget, QHBoxLayout, QVBoxLayout, QGraphicsOpacityEffect
)
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

# (Opsional) Jika PATH belum di-set, coba tambahkan direktori VLC ini dulu
if sys.platform == "win32":
    vlc_dir = r"C:\Program Files\VideoLAN\VLC"
    if os.path.isdir(vlc_dir):
        try:
            os.add_dll_directory(vlc_dir)  # Windows 10 1803+
        except (AttributeError, FileNotFoundError):
            os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")

import vlc  # impor setelah memastikan PATH

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python VLC Video Player")
        self.resize(960, 540)

        # --- LibVLC ---
        self.vlc_instance = vlc.Instance()
        self.mediaplayer = self.vlc_instance.media_player_new()

        # --- UI ---
        self.central = QWidget(self)
        self.setCentralWidget(self.central)

        self.video_frame = QFrame(self.central)
        self.video_frame.setFrameShape(QFrame.NoFrame)
        self.video_frame.setMinimumSize(840, 460)

        # --- Kontrol bar & progress bar dalam QWidget dengan background transparan ---
        self.controls_widget = QWidget(self.central)
        self.controls_widget.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # Ubah nilai alpha dari 180 ke 0 untuk membuat background transparan
        self.controls_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
        self.controls_widget.setAutoFillBackground(False)

        self.progress_widget = QWidget(self.central)
        self.progress_widget.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # Ubah nilai alpha dari 180 ke 0 untuk membuat background transparan
        self.progress_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
        self.progress_widget.setAutoFillBackground(False)

        # Tombol dan slider seperti sebelumnya...
        self.btn_open = QPushButton("Open")
        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon("assets/icons/play.png"))
        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(QIcon("assets/icons/stop.png"))
        self.btn_fullscreen = QPushButton()
        self.btn_fullscreen.setIcon(QIcon("assets/icons/fullscreen.png"))
        self.btn_fullscreen.setToolTip("Fullscreen")
        self.slider_pos = QSlider(QtCore.Qt.Horizontal)
        self.slider_pos.setRange(0, 1000)
        self.slider_pos.setSingleStep(1)
        self.slider_pos.setEnabled(False)
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setMinimumWidth(120)
        self.slider_volume = QSlider(QtCore.Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.lbl_vol = QLabel("Vol")

        # Layout untuk widget progress dan kontrol
        controls_row1 = QHBoxLayout()
        controls_row1.addWidget(self.btn_open)                # Paling kiri
        controls_row1.addStretch()
        controls_row1.addWidget(self.btn_play)
        controls_row1.addWidget(self.btn_stop)
        controls_row1.addWidget(self.lbl_vol)
        self.slider_volume.setFixedWidth(70)
        controls_row1.addWidget(self.slider_volume)
        controls_row1.addStretch()
        controls_row1.addWidget(self.btn_fullscreen)          # Paling kanan
        self.controls_widget.setLayout(controls_row1)

        controls_row2 = QHBoxLayout()
        controls_row2.addStretch()
        controls_row2.addWidget(self.slider_pos)
        controls_row2.addWidget(self.lbl_time)
        controls_row2.addStretch()
        self.progress_widget.setLayout(controls_row2)

        # Root layout
        root = QVBoxLayout(self.central)
        root.addWidget(self.video_frame, stretch=9)
        root.addWidget(self.progress_widget)
        root.addWidget(self.controls_widget, stretch=1)

        # --- Signal ---
        self.btn_open.clicked.connect(self.open_file)
        self.btn_play.clicked.connect(self.play_pause)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.slider_pos.sliderPressed.connect(self.pause_update)
        self.slider_pos.sliderReleased.connect(self.set_position_from_slider)
        self.slider_volume.valueChanged.connect(self.set_volume)

        # --- Timer UI update ---
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_ui)

        self.user_is_seeking = False
        self.is_playing = False
        self.is_fullscreen = False

        # --- Hide controls timer (diubah menjadi 1.5 detik) ---
        self.hide_controls_timer = QtCore.QTimer(self)
        self.hide_controls_timer.setInterval(1500)  # 1.5 detik
        self.hide_controls_timer.timeout.connect(self.hide_controls)
        self.hide_controls_timer.setSingleShot(True)  # Timer hanya berjalan sekali

        # Untuk tracking apakah controls sedang visible
        self.controls_visible = True

        # Event filter untuk mouse movement - pasang ke video_frame juga
        self.installEventFilter(self)
        self.video_frame.installEventFilter(self)
        self.central.installEventFilter(self)
        
        # Setup untuk fade effect menggunakan QGraphicsOpacityEffect
        self.controls_opacity_effect = QGraphicsOpacityEffect()
        self.progress_opacity_effect = QGraphicsOpacityEffect()
        
        # Animasi untuk smooth hide/show controls
        self.controls_animation = QPropertyAnimation(self.controls_opacity_effect, b"opacity")
        self.controls_animation.setDuration(300)
        self.controls_animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        self.progress_animation = QPropertyAnimation(self.progress_opacity_effect, b"opacity")
        self.progress_animation.setDuration(300)
        self.progress_animation.setEasingCurve(QEasingCurve.InOutCubic)

    # --- Helpers ---
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv);;All Files (*.*)"
        )
        if not path:
            return

        media = self.vlc_instance.media_new(path)
        self.mediaplayer.set_media(media)

        # Set output video ke frame kita
        if sys.platform.startswith("linux"):  # X11
            self.mediaplayer.set_xwindow(int(self.video_frame.winId()))
        elif sys.platform == "win32":
            self.mediaplayer.set_hwnd(int(self.video_frame.winId()))
        elif sys.platform == "darwin":
            self.mediaplayer.set_nsobject(int(self.video_frame.winId()))

        self.btn_play.setText("")
        self.btn_play.setIcon(QIcon("assets/icons/play.png"))
        self.is_playing = False
        self.slider_pos.setEnabled(True)
        self.play_pause()  # auto play setelah open

    def play_pause(self):
        if self.mediaplayer is None:
            return
        state = self.mediaplayer.get_state()
        if state in (vlc.State.Playing, vlc.State.Buffering):
            self.mediaplayer.pause()
            self.btn_play.setText("")
            self.btn_play.setIcon(QIcon("assets/icons/play.png"))
            self.is_playing = False
            self.timer.stop()
        else:
            self.mediaplayer.play()
            self.btn_play.setText("")
            self.btn_play.setIcon(QIcon("assets/icons/pause.png"))
            self.is_playing = True
            QtCore.QTimer.singleShot(100, self.timer.start)  # mulai update UI

    def stop(self):
        if self.mediaplayer:
            self.mediaplayer.stop()
        self.btn_play.setText("")
        self.btn_play.setIcon(QIcon("assets/icons/play.png"))
        self.is_playing = False
        self.timer.stop()
        self.slider_pos.setValue(0)
        self.lbl_time.setText("00:00 / 00:00")

    def set_volume(self, value: int):
        if self.mediaplayer:
            self.mediaplayer.audio_set_volume(int(value))

    def ms_to_string(self, ms: int) -> str:
        if ms <= 0 or ms is None:
            return "00:00"
        s = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}" if h else f"{int(m):02d}:{int(s):02d}"

    def update_ui(self):
        if not self.mediaplayer or self.user_is_seeking:
            return

        length = self.mediaplayer.get_length()  # ms
        time_ms = self.mediaplayer.get_time()   # ms

        # Update slider
        if length > 0:
            pos = self.mediaplayer.get_position()  # 0.0 - 1.0
            self.slider_pos.blockSignals(True)
            self.slider_pos.setValue(int(pos * 1000))
            self.slider_pos.blockSignals(False)

            # Update label waktu
            self.lbl_time.setText(f"{self.ms_to_string(time_ms)} / {self.ms_to_string(length)}")

        # Auto-stop saat selesai
        state = self.mediaplayer.get_state()
        if state in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
            self.stop()

    def pause_update(self):
        self.user_is_seeking = True

    def set_position_from_slider(self):
        if not self.mediaplayer:
            return
        val = self.slider_pos.value() / 1000.0  # 0.0 - 1.0
        self.mediaplayer.set_position(val)
        self.user_is_seeking = False

    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.showFullScreen()
            self.btn_fullscreen.setIcon(QIcon("assets/icons/exit-fullscreen.png"))
            self.btn_fullscreen.setToolTip("Exit Fullscreen")
            self.is_fullscreen = True

            # Posisikan controls floating di atas video
            self.setup_fullscreen_controls()
            
            # Mulai timer untuk hide controls
            self.hide_controls_timer.start()
            
        else:
            self.showNormal()
            self.btn_fullscreen.setIcon(QIcon("assets/icons/fullscreen.png"))
            self.btn_fullscreen.setToolTip("Fullscreen")
            self.is_fullscreen = False

            # Stop timer hide controls
            self.hide_controls_timer.stop()
            
            # Kembalikan controls ke layout normal
            self.restore_normal_controls()

    def setup_fullscreen_controls(self):
        """Setup floating controls untuk mode fullscreen"""
        # Lepaskan dari layout dan buat floating
        self.controls_widget.setParent(self)
        self.progress_widget.setParent(self)
        self.controls_widget.raise_()
        self.progress_widget.raise_()
        
        # Apply opacity effects
        self.controls_widget.setGraphicsEffect(self.controls_opacity_effect)
        self.progress_widget.setGraphicsEffect(self.progress_opacity_effect)
        
        # Set opacity penuh
        self.controls_opacity_effect.setOpacity(1.0)
        self.progress_opacity_effect.setOpacity(1.0)
        
        # Update posisi controls
        self.update_fullscreen_controls_position()
        
        # Set style untuk fullscreen dengan background transparan
        self.controls_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
        self.progress_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
        
        # Pastikan widget terlihat
        self.controls_widget.show()
        self.progress_widget.show()
        
        # Set flag controls visible
        self.controls_visible = True

    def restore_normal_controls(self):
        """Kembalikan controls ke posisi normal"""
        # Remove opacity effects
        self.controls_widget.setGraphicsEffect(None)
        self.progress_widget.setGraphicsEffect(None)
        
        # Pastikan controls visible
        self.controls_widget.show()
        self.progress_widget.show()
        self.controls_visible = True
        
        # Kembalikan ke central widget dan layout
        self.controls_widget.setParent(self.central)
        self.progress_widget.setParent(self.central)
        
        # Add kembali ke layout
        layout = self.central.layout()
        layout.addWidget(self.progress_widget)
        layout.addWidget(self.controls_widget)
        
        # Reset style dengan background transparan
        self.controls_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
        self.progress_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
        
        # Show cursor
        self.setCursor(QCursor(QtCore.Qt.ArrowCursor))

    def update_fullscreen_controls_position(self):
        """Update posisi controls saat fullscreen"""
        if not self.is_fullscreen:
            return
            
        screen_geometry = self.geometry()
        
        # Progress bar - posisi di bagian bawah tengah
        progress_width = screen_geometry.width() * 3 // 4
        progress_height = 36
        progress_x = (screen_geometry.width() - progress_width) // 2
        progress_y = screen_geometry.height() - 110
        
        self.progress_widget.setGeometry(progress_x, progress_y, progress_width, progress_height)
        
        # Controls bar - di bawah progress bar
        controls_width = screen_geometry.width() * 3 // 4
        controls_height = 48
        controls_x = (screen_geometry.width() - controls_width) // 2
        controls_y = screen_geometry.height() - 60
        
        self.controls_widget.setGeometry(controls_x, controls_y, controls_width, controls_height)

    def show_controls(self):
        """Tampilkan controls dengan animasi"""
        if not self.controls_visible:
            # Pastikan widget terlihat dulu
            self.controls_widget.show()
            self.progress_widget.show()
            
            # Animasi fade in
            self.controls_animation.setStartValue(0.0)
            self.controls_animation.setEndValue(1.0)
            self.controls_animation.start()
            
            self.progress_animation.setStartValue(0.0)
            self.progress_animation.setEndValue(1.0)
            self.progress_animation.start()
            
            self.controls_visible = True
        else:
            # Jika sudah visible, pastikan opacity penuh
            if self.is_fullscreen:
                self.controls_opacity_effect.setOpacity(1.0)
                self.progress_opacity_effect.setOpacity(1.0)
            
        # Show cursor
        self.setCursor(QCursor(QtCore.Qt.ArrowCursor))
        
        # Set style dengan background transparan untuk fullscreen
        if self.is_fullscreen:
            self.controls_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")
            self.progress_widget.setStyleSheet("background: rgba(30,30,30,0); border-radius: 10px;")

        # Pastikan widget tampil setelah animasi
        self.controls_widget.show()
        self.progress_widget.show()

    def hide_controls(self):
        """Sembunyikan controls dengan animasi"""
        if self.is_fullscreen and self.controls_visible:
            # Animasi fade out - tidak hide widget, hanya set opacity
            self.controls_animation.setStartValue(1.0)
            self.controls_animation.setEndValue(0.0)
            self.controls_animation.start()
            
            self.progress_animation.setStartValue(1.0)
            self.progress_animation.setEndValue(0.0)
            self.progress_animation.start()
            
            self.controls_visible = False
            
            # Hide cursor
            self.setCursor(QCursor(QtCore.Qt.BlankCursor))

            # Sembunyikan widget setelah animasi selesai
            self.controls_animation.finished.connect(self.controls_widget.hide)
            self.progress_animation.finished.connect(self.progress_widget.hide)

    def keyPressEvent(self, event):
        # ESC untuk keluar fullscreen
        if event.key() == QtCore.Qt.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen()
        # Spacebar untuk play/pause
        elif event.key() == QtCore.Qt.Key_Space:
            self.play_pause()
            # Show controls saat user menekan tombol
            if self.is_fullscreen:
                self.show_controls()
                self.hide_controls_timer.start()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update posisi controls saat resize dalam fullscreen
        if self.is_fullscreen:
            self.update_fullscreen_controls_position()

    def mouseMoveEvent(self, event):
        """Handle mouse movement untuk show controls"""
        if self.is_fullscreen:
            self.show_controls()
            self.hide_controls_timer.start()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click untuk show controls"""
        if self.is_fullscreen:
            self.show_controls()
            self.hide_controls_timer.start()
        super().mousePressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())