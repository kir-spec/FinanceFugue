"""Генерация PDF-счетов (инвойсов) для заказов.

Использует reportlab для создания профессиональных документов
с таблицей платежей, итогами и реквизитами клиента.
"""
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

from ..models import Client, Order
from ..logger import get_logger

logger = get_logger("InvoiceGenerator")

# --- Регистрация кириллического шрифта ---
_FONT_REGISTERED = False

def _ensure_font() -> str:
    """Находит и регистрирует кириллический шрифт. Возвращает имя шрифта."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return "CyrFont"

    # Пробуем системные шрифты Windows
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "calibri.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "tahoma.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"),
    ]
    for path in candidates:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("CyrFont", path))
            _FONT_REGISTERED = True
            logger.info("Зарегистрирован шрифт: %s", path)
            return "CyrFont"

    # Если ничего не нашли — reportlab будет использовать Helvetica
    logger.warning("Кириллический шрифт не найден, используется Helvetica")
    return "Helvetica"


def _currency_symbol(currency: str) -> str:
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "UAH": "₴", "BYN": "Br"}
    return symbols.get(currency, currency)


def generate_invoice(
    client: Client,
    order: Order,
    output_dir: str,
    *,
    seller_name: str = "FinanceFugue CRM",
    seller_info: str = "",
    seller_requisites: str = "",
) -> str:
    """Генерирует PDF-счёт для конкретного заказа и возвращает путь к файлу."""

    font_name = _ensure_font()
    cur = _currency_symbol(order.currency)

    # Имя файла
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in client.name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Invoice_{safe_name}_{order.id[:8]}_{timestamp}.pdf"
    output_path = os.path.join(output_dir, filename)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # --- Стили ---
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "InvoiceTitle", parent=styles["Title"],
        fontName=font_name, fontSize=22, leading=26,
        textColor=colors.HexColor("#0078D7"),
    )
    style_heading = ParagraphStyle(
        "InvoiceHeading", parent=styles["Heading2"],
        fontName=font_name, fontSize=13, leading=16,
        textColor=colors.HexColor("#333333"),
        spaceAfter=4 * mm,
    )
    style_normal = ParagraphStyle(
        "InvoiceNormal", parent=styles["Normal"],
        fontName=font_name, fontSize=10, leading=13,
    )
    style_small = ParagraphStyle(
        "InvoiceSmall", parent=styles["Normal"],
        fontName=font_name, fontSize=8, leading=10,
        textColor=colors.HexColor("#888888"),
    )

    elements = []

    # --- Шапка ---
    elements.append(Paragraph("СЧЁТ / INVOICE", style_title))
    elements.append(Spacer(1, 3 * mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0078D7")))
    elements.append(Spacer(1, 5 * mm))

    # --- Информация о продавце и покупателе ---
    # Собираем блок исполнителя
    seller_lines = f"<b>Исполнитель:</b><br/>{seller_name}"
    if seller_info:
        seller_lines += f"<br/>{seller_info}"
    if seller_requisites:
        req_html = seller_requisites.replace("\n", "<br/>")
        seller_lines += f"<br/><br/><b>Реквизиты:</b><br/>{req_html}"

    # Собираем блок заказчика
    client_lines = f"<b>Заказчик:</b><br/>{client.name}"
    if client.email:
        client_lines += f"<br/>Email: {client.email}"
    if client.social_link:
        client_lines += f"<br/>Ссылка: {client.social_link}"
    if client.requisites:
        req_html = client.requisites.replace("\n", "<br/>")
        client_lines += f"<br/><br/><b>Реквизиты:</b><br/>{req_html}"

    info_data = [
        [
            Paragraph(seller_lines, style_normal),
            Paragraph(client_lines, style_normal),
        ]
    ]
    info_table = Table(info_data, colWidths=[250, 250])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # --- Информация о заказе ---
    elements.append(Paragraph("Детали заказа", style_heading))
    order_info_data = [
        ["Услуга", order.service_type],
        ["ID заказа", order.id],
        ["Дата создания", order.created_at or "—"],
        ["Дедлайн", order.deadline or "—"],
        ["Статус", order.status],
    ]
    order_table = Table(order_info_data, colWidths=[120, 380])
    order_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#666666")),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#EEEEEE")),
    ]))
    elements.append(order_table)
    elements.append(Spacer(1, 6 * mm))

    # --- Таблица платежей ---
    if order.payments:
        elements.append(Paragraph("История платежей", style_heading))
        pay_header = ["Дата", "Тип", "Сумма", "Примечание"]
        pay_rows = [pay_header]
        for p in order.payments:
            pay_rows.append([
                p.date or "—",
                p.type.capitalize(),
                f"{p.amount:,.2f} {cur}",
                p.note or "—",
            ])

        pay_table = Table(pay_rows, colWidths=[100, 80, 100, 220])
        pay_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            # Шапка
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0078D7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            # Тело
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(pay_table)
        elements.append(Spacer(1, 6 * mm))

    # --- Итоги ---
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("Финансовый итог", style_heading))

    summary_data = [
        ["Стоимость заказа:", f"{order.price:,.2f} {cur}"],
        ["Аванс (договор):", f"{order.advance:,.2f} {cur}"],
        ["Всего получено:", f"{order.total_received:,.2f} {cur}"],
        ["Остаток долга:", f"{order.debt:,.2f} {cur}"],
    ]
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, -1), (1, -1), font_name),
        ("TEXTCOLOR", (1, -1), (1, -1), colors.HexColor("#DC3545") if order.debt > 0 else colors.HexColor("#28A745")),
        ("FONTSIZE", (0, -1), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#0078D7")),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 10 * mm))

    # --- Подвал ---
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    elements.append(Paragraph(
        f"Документ сформирован автоматически: {generated_at} • {seller_name}",
        style_small,
    ))

    doc.build(elements)
    logger.info("PDF-счёт сгенерирован: %s", output_path)
    return output_path
