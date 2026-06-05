"""Keep OrderWidget init_ui + toggle_contents only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "src/widgets/order_widget.py"
text = path.read_text(encoding="utf-8")
marker = "    # Drag and drop методы"
idx = text.find(marker)
if idx < 0:
    raise SystemExit("marker not found")

toggle_pat = "    def toggle_contents(self):"
tidx = text.find(toggle_pat, idx)
if tidx < 0:
    raise SystemExit("toggle not found")
# find end of toggle_contents method
end = text.find("\n    def ", tidx + 1)
if end < 0:
    end = len(text)
toggle_block = text[tidx:end].rstrip()

header = text[:idx].rstrip()
header = header.replace(
    "class OrderWidget(QFrame):",
    "class OrderWidget(OrderFinancialMixin, OrderFilesMixin, QFrame):",
)
header = header.replace(
    "from .file_item_widget import FileItemWidget",
    "from .file_item_widget import FileItemWidget\nfrom .order_files_mixin import OrderFilesMixin\nfrom .order_financial_mixin import OrderFinancialMixin",
)

path.write_text(header + "\n\n" + toggle_block + "\n", encoding="utf-8")
print("trimmed", path)
