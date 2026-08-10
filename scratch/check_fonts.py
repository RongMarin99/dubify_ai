from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
import sys

app = QApplication(sys.argv)
families = QFontDatabase.families()
khmer_fonts = [f for f in families if 'khmer' in f.lower() or 'leelawadee' in f.lower() or 'battambang' in f.lower()]
print("=== Installed Khmer/Leelawadee Fonts ===")
for f in khmer_fonts:
    print(f"  {f}")
if not khmer_fonts:
    print("  (NONE FOUND)")
app.quit()
