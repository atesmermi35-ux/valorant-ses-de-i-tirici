import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "GUI smoke requires a display")
class GuiSmokeTests(unittest.TestCase):
    def test_window_profile_and_persisted_engine(self):
        import tkinter as tk
        from voicebridge import core
        from voicebridge.gui import App, PROFILES
        with tempfile.TemporaryDirectory() as directory:
            root = tk.Tk()
            try:
                app = App(root, Path(directory))
                root.update()
                self.assertIn("VOICEBRIDGE", app.root.title().upper())
                self.assertTrue(app.install_button.instate(["disabled"]))
                self.assertTrue(app.launch_button.instate(["disabled"]))
                self.assertIn("RTX 3050", app.profile_text.get("1.0", "end"))
                app.store_launcher(Path(directory) / "start_http.bat")
                self.assertFalse(app.launch_button.instate(["disabled"]))
                self.assertIn("launcher", core.read_config(Path(directory)))
                app.profile_box.current(1)
                app.profile_box.event_generate("<<ComboboxSelected>>")
                root.update()
                self.assertIn("FPS", app.profile_text.get("1.0", "end"))
                with patch.object(app.gpu_status, "set") as set_value:
                    app.events.put(("success", (app.gpu_status.set, "GPU fixture")))
                    app.poll()
                    set_value.assert_called_with("GPU fixture")
                self.assertEqual(len(PROFILES), 3)
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
