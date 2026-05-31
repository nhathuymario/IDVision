"""
IDVision — Salary Slip PDF Generator
Generates professional salary slips using fpdf2 with Vietnamese support.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)

# Font directory relative to this file
FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"


@dataclass
class SlipItem:
    """A single earning or deduction line item."""
    label: str
    amount: float


@dataclass
class SalarySlipData:
    """All data needed to render a salary slip PDF."""
    # Company info
    company_name: str = "IDVision"
    company_address: str = ""
    company_phone: str = ""

    # Employee info
    employee_name: str = ""
    employee_code: str = ""
    department: str = ""

    # Period
    month: str = ""  # e.g. "2026-05"

    # Attendance summary
    worked_days: int = 0
    worked_hours: float = 0.0
    hourly_wage: float = 0.0
    base_salary: float = 0.0

    # Extra items (admin-customizable)
    extra_earnings: list[SlipItem] = field(default_factory=list)
    extra_deductions: list[SlipItem] = field(default_factory=list)

    # Footer
    footer_note: str = ""
    generated_at: str = ""


class SalarySlipPDF(FPDF):
    """Custom PDF class for salary slips with Vietnamese font support."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._register_fonts()

    def _register_fonts(self):
        """Register DejaVu Sans fonts for Vietnamese text."""
        regular = FONT_DIR / "DejaVuSans.ttf"
        bold = FONT_DIR / "DejaVuSans-Bold.ttf"

        if not regular.exists():
            logger.error(f"Font not found: {regular}")
            raise FileNotFoundError(f"DejaVuSans.ttf not found in {FONT_DIR}")

        self.add_font("DejaVu", "", str(regular), uni=True)
        if bold.exists():
            self.add_font("DejaVu", "B", str(bold), uni=True)
        else:
            # Fallback: use regular as bold too
            self.add_font("DejaVu", "B", str(regular), uni=True)

    def header(self):
        """Override: no default header."""
        pass

    def footer(self):
        """Override: page number at bottom."""
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Trang {self.page_no()}/{{nb}}", align="C")


def _format_currency(amount: float) -> str:
    """Format number as VND currency string."""
    if amount == int(amount):
        return f"{int(amount):,}".replace(",", ".") + " đ"
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " đ"


def _format_month_display(month_str: str) -> str:
    """Convert 'YYYY-MM' to 'Tháng MM/YYYY'."""
    try:
        parts = month_str.split("-")
        return f"Tháng {parts[1]}/{parts[0]}"
    except (IndexError, ValueError):
        return month_str


def generate_salary_slip(data: SalarySlipData) -> bytes:
    """Generate a salary slip PDF and return it as bytes.

    Args:
        data: SalarySlipData with all slip information.

    Returns:
        PDF file content as bytes.
    """
    pdf = SalarySlipPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    page_width = pdf.w - 20  # 10mm margin each side

    # ── Header: Company Info ──────────────────────────────────
    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(30, 58, 138)  # Dark blue
    pdf.cell(0, 10, data.company_name, align="C", new_x="LMARGIN", new_y="NEXT")

    if data.company_address:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, data.company_address, align="C", new_x="LMARGIN", new_y="NEXT")

    if data.company_phone:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f"ĐT: {data.company_phone}", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # ── Title ─────────────────────────────────────────────────
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(0, 0, 0)
    month_display = _format_month_display(data.month)
    pdf.cell(0, 10, f"PHIẾU LƯƠNG — {month_display}", align="C", new_x="LMARGIN", new_y="NEXT")

    # Decorative line
    pdf.set_draw_color(30, 58, 138)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(8)

    # ── Employee Info Section ─────────────────────────────────
    _draw_section_title(pdf, "THÔNG TIN NHÂN VIÊN")

    info_items = [
        ("Họ và Tên", data.employee_name),
        ("Mã nhân viên", data.employee_code),
    ]
    if data.department:
        info_items.append(("Phòng ban", data.department))

    for label, value in info_items:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(50, 7, f"{label}:", new_x="END")
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # ── Attendance Summary Section ────────────────────────────
    _draw_section_title(pdf, "THỐNG KÊ CHẤM CÔNG")

    attendance_items = [
        ("Số ngày công", str(data.worked_days)),
        ("Tổng giờ công", f"{data.worked_hours:.2f} giờ"),
        ("Đơn giá/giờ", _format_currency(data.hourly_wage)),
    ]

    for label, value in attendance_items:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(50, 7, f"{label}:", new_x="END")
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # ── Salary Table ──────────────────────────────────────────
    _draw_section_title(pdf, "CHI TIẾT LƯƠNG")

    # Table header
    col_label_w = page_width * 0.65
    col_amount_w = page_width * 0.35

    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(col_label_w, 8, "  Khoản mục", fill=True, new_x="END")
    pdf.cell(col_amount_w, 8, "Số tiền (VND)", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    # Reset text color
    pdf.set_text_color(0, 0, 0)
    row_fill = False

    # Base salary row
    _draw_table_row(pdf, col_label_w, col_amount_w, "Lương cơ bản (giờ công × đơn giá)", data.base_salary, row_fill)
    row_fill = not row_fill

    # Extra earnings
    total_earnings = data.base_salary
    for item in data.extra_earnings:
        _draw_table_row(pdf, col_label_w, col_amount_w, f"(+) {item.label}", item.amount, row_fill)
        total_earnings += item.amount
        row_fill = not row_fill

    # Extra deductions
    total_deductions = 0.0
    for item in data.extra_deductions:
        _draw_table_row(pdf, col_label_w, col_amount_w, f"(−) {item.label}", -item.amount, row_fill, is_deduction=True)
        total_deductions += item.amount
        row_fill = not row_fill

    # Separator line
    pdf.set_draw_color(30, 58, 138)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(2)

    # Net salary (total)
    net_salary = total_earnings - total_deductions
    pdf.set_font("DejaVu", "B", 12)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(col_label_w, 10, "  THỰC LÃNH", new_x="END")
    pdf.cell(col_amount_w, 10, _format_currency(net_salary), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)

    # ── Footer Note ───────────────────────────────────────────
    if data.footer_note:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, data.footer_note)
        pdf.ln(3)

    # Generated timestamp
    gen_time = data.generated_at or datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Ngày tạo: {gen_time}", align="R", new_x="LMARGIN", new_y="NEXT")

    # ── Signature Area ────────────────────────────────────────
    pdf.ln(15)
    half_w = page_width / 2

    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(0, 0, 0)

    x_start = pdf.get_x()
    pdf.cell(half_w, 7, "Người lập phiếu", align="C", new_x="END")
    pdf.cell(half_w, 7, "Người nhận", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(half_w, 5, "(Ký, ghi rõ họ tên)", align="C", new_x="END")
    pdf.cell(half_w, 5, "(Ký, ghi rõ họ tên)", align="C", new_x="LMARGIN", new_y="NEXT")

    # Return PDF bytes
    return pdf.output()


def _draw_section_title(pdf: FPDF, title: str):
    """Draw a section title with a subtle background."""
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 8, f"▸ {title}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _draw_table_row(
    pdf: FPDF,
    col_label_w: float,
    col_amount_w: float,
    label: str,
    amount: float,
    fill: bool,
    is_deduction: bool = False,
):
    """Draw a single row in the salary table."""
    if fill:
        pdf.set_fill_color(245, 247, 250)
    else:
        pdf.set_fill_color(255, 255, 255)

    pdf.set_font("DejaVu", "", 10)

    if is_deduction:
        pdf.set_text_color(180, 30, 30)
    else:
        pdf.set_text_color(0, 0, 0)

    pdf.cell(col_label_w, 7, f"  {label}", fill=fill, new_x="END")
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(col_amount_w, 7, _format_currency(abs(amount)), fill=fill, align="R", new_x="LMARGIN", new_y="NEXT")

    # Reset color
    pdf.set_text_color(0, 0, 0)
