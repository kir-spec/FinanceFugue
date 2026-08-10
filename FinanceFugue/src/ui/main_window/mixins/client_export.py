import json
import os
import shutil
import zipfile
from datetime import datetime

from PySide6.QtWidgets import QFileDialog, QMessageBox, QDialog

from ....dialogs import ClientOrdersExportDialog
from ....logger import get_logger
from ....utils.path_safety import sanitize_path_component as _sanitize_filename

logger = get_logger("MainWindow")


class ClientExportMixin:
    def export_client_files(self):
        """Экспорт всех файлов клиента с объяснением"""
        if not self.current_client:
            return

        explanation = QMessageBox(self)
        explanation.setWindowTitle("Экспорт файлов клиента")
        explanation.setText(
            "Эта функция экспортирует все файлы из всех заказов клиента.\n\n"
            "Для каждого заказа будет создан отдельный ZIP архив, содержащий все файлы этого заказа.\n"
            "Архивы будут сохранены в выбранной вами папке, сгруппированные по датам заказов."
        )
        explanation.setIcon(QMessageBox.Icon.Information)
        explanation.addButton("Продолжить", QMessageBox.ButtonRole.AcceptRole)
        explanation.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)

        if explanation.exec() != 0:
            return

        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для экспорта файлов")
        if not folder:
            return

        total_files = 0
        exported_orders = 0

        for order in self.current_client.orders:
            if not order.files:
                continue

            ready_files = [f for f in order.files if os.path.exists(f.path)]
            if not ready_files:
                continue

            try:
                order_date = datetime.strptime(order.created_at.split()[0], "%d.%m.%Y")
                date_folder = os.path.join(folder, order_date.strftime("%Y-%m-%d"))
            except (ValueError, IndexError):
                date_folder = os.path.join(folder, "без_даты")

            os.makedirs(date_folder, exist_ok=True)

            safe_service = _sanitize_filename(order.service_type)
            safe_id = _sanitize_filename(order.id[:8])
            archive_name = f"{safe_service}_{safe_id}.zip"
            if not archive_name.strip("._"):
                archive_name = f"order_{safe_id}.zip"
            archive_path = os.path.join(date_folder, archive_name)

            try:
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in ready_files:
                        z.write(f.path, f.name)
                        total_files += 1

                exported_orders += 1
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Не удалось создать архив для заказа '{order.service_type}': {e}",
                )

        if exported_orders > 0:
            QMessageBox.information(
                self,
                "Экспорт завершен",
                f"Экспортировано заказов: {exported_orders}\n"
                f"Экспортировано файлов: {total_files}\n"
                f"Папка: {folder}",
            )
        else:
            QMessageBox.information(self, "Нет файлов", "У клиента нет файлов для экспорта.")

    def export_client_orders(self):
        """Экспорт заказов клиента с выбором опций"""
        if not self.current_client:
            return

        dialog = ClientOrdersExportDialog(self.current_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            export_data = dialog.get_export_data()

            if not export_data["selected_orders"]:
                QMessageBox.warning(self, "Ошибка", "Не выбрано ни одного заказа для экспорта")
                return

            folder = QFileDialog.getExistingDirectory(self, "Выберите папку для экспорта")
            if not folder:
                return

            safe_name = _sanitize_filename(self.current_client.name)
            json_path = os.path.join(folder, f"{safe_name}_заказы.json")
            try:
                orders_data = []
                for order in export_data["selected_orders"]:
                    order_dict = {
                        "id": order.id,
                        "service_type": order.service_type,
                        "price": order.price,
                        "advance": order.advance,
                        "created_at": order.created_at,
                        "deadline": order.deadline,
                        "status": order.status,
                        "files": [{"name": f.name, "path": f.path} for f in order.files],
                        "payments": [p.to_dict() for p in order.payments],
                    }
                    orders_data.append(order_dict)

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(orders_data, f, ensure_ascii=False, indent=4)

                if export_data["include_files"]:
                    files_folder = os.path.join(folder, "файлы_заказов")
                    os.makedirs(files_folder, exist_ok=True)

                    for order in export_data["selected_orders"]:
                        order_folder = os.path.join(
                            files_folder, _sanitize_filename(order.service_type)
                        )
                        os.makedirs(order_folder, exist_ok=True)

                        for file in order.files:
                            if os.path.exists(file.path):
                                try:
                                    shutil.copy2(file.path, os.path.join(order_folder, file.name))
                                except Exception as e:
                                    logger.error("Ошибка копирования файла %s: %s", file.name, e)

                QMessageBox.information(
                    self,
                    "Экспорт завершен",
                    f"Экспортировано заказов: {len(export_data['selected_orders'])}\n"
                    f"JSON файл: {json_path}\n"
                    f"{'Файлы экспортированы в отдельную папку' if export_data['include_files'] else 'Файлы не экспортированы'}",
                )

            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать заказы: {e}")

    def _export_client_files_for(self, client):
        prev = self.current_client
        self.current_client = client
        try:
            self.export_client_files()
        finally:
            self.current_client = prev
