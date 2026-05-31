"""
IDVision — Salary Router
Admin endpoints for month-based payroll summaries, PDF generation,
salary slip template configuration, and Telegram sending.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Employee, SalarySlipConfig
from routers.auth import verify_admin_token
from schemas import (
    SalaryEmployeeDetailResponse,
    SalaryEmployeeSummary,
    SalaryOverviewResponse,
    SalarySlipConfigResponse,
    SalarySlipConfigUpdate,
    SalarySendRequest,
    SalarySendResult,
    SlipItemSchema,
)
from services.payroll import (
    calculate_employee_month_stats,
    get_or_create_policy,
)
from services.salary_pdf import SalarySlipData, SlipItem, generate_salary_slip
from services.telegram_bot import telegram_notifier

router = APIRouter(prefix="/api/admin/salary", tags=["Admin Salary"])


def _resolve_month(month: str | None) -> str:
    if month:
        try:
            datetime.strptime(month, "%Y-%m")
            return month
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="month must be in YYYY-MM format") from exc
    return datetime.now().strftime("%Y-%m")


async def _get_or_create_slip_config(session: AsyncSession) -> SalarySlipConfig:
    """Get the salary slip config, creating a default if none exists."""
    result = await session.execute(select(SalarySlipConfig).limit(1))
    config = result.scalar_one_or_none()
    if config:
        return config

    config = SalarySlipConfig(
        company_name="IDVision",
        company_address="",
        company_phone="",
        extra_earnings=[],
        extra_deductions=[],
        footer_note="Phiếu lương này được tạo tự động bởi hệ thống IDVision.",
    )
    session.add(config)
    await session.flush()
    return config


# ── Salary Overview & Detail ─────────────────────────────────

@router.get("/overview", response_model=SalaryOverviewResponse)
async def salary_overview(
    month: str | None = Query(None, description="YYYY-MM"),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    target_month = _resolve_month(month)
    policy = await get_or_create_policy(session)
    result = await session.execute(
        select(Employee)
        .where(and_(Employee.is_active == True))
        .order_by(Employee.name.asc())
    )
    employees = result.scalars().all()
    items: list[SalaryEmployeeSummary] = []
    total_days = 0
    total_hours = 0.0
    total_salary = 0.0
    for employee in employees:
        stats = await calculate_employee_month_stats(session, employee.id, target_month, policy)
        estimated_salary = round(stats.worked_hours * policy.hourly_wage, 2)
        total_days += stats.worked_days
        total_hours += stats.worked_hours
        total_salary += estimated_salary
        items.append(
            SalaryEmployeeSummary(
                employee_id=employee.id,
                employee_name=employee.name,
                employee_code=employee.employee_code,
                worked_days=stats.worked_days,
                worked_hours=stats.worked_hours,
                hourly_wage=float(policy.hourly_wage),
                estimated_salary=estimated_salary,
                telegram_linked=bool(employee.telegram_chat_id),
            )
        )
    return SalaryOverviewResponse(
        month=target_month,
        total_employees=len(items),
        total_worked_days=total_days,
        total_worked_hours=round(total_hours, 2),
        total_estimated_salary=round(total_salary, 2),
        employees=items,
    )


@router.get("/employee/{employee_id}", response_model=SalaryEmployeeDetailResponse)
async def salary_employee_detail(
    employee_id: int,
    month: str | None = Query(None, description="YYYY-MM"),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    target_month = _resolve_month(month)
    policy = await get_or_create_policy(session)
    result = await session.execute(
        select(Employee).where(and_(Employee.id == employee_id, Employee.is_active == True))
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    stats = await calculate_employee_month_stats(session, employee.id, target_month, policy)
    estimated_salary = round(stats.worked_hours * policy.hourly_wage, 2)
    return SalaryEmployeeDetailResponse(
        month=target_month,
        employee=SalaryEmployeeSummary(
            employee_id=employee.id,
            employee_name=employee.name,
            employee_code=employee.employee_code,
            worked_days=stats.worked_days,
            worked_hours=stats.worked_hours,
            hourly_wage=float(policy.hourly_wage),
            estimated_salary=estimated_salary,
            telegram_linked=bool(employee.telegram_chat_id),
        ),
    )


# ── Salary Slip Config (Template) ────────────────────────────

@router.get("/slip-config", response_model=SalarySlipConfigResponse)
async def get_slip_config(
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Get the current salary slip template configuration."""
    config = await _get_or_create_slip_config(session)
    return SalarySlipConfigResponse(
        company_name=config.company_name,
        company_address=config.company_address or "",
        company_phone=config.company_phone or "",
        extra_earnings=[SlipItemSchema(**e) for e in (config.extra_earnings or [])],
        extra_deductions=[SlipItemSchema(**d) for d in (config.extra_deductions or [])],
        footer_note=config.footer_note or "",
    )


@router.put("/slip-config", response_model=SalarySlipConfigResponse)
async def update_slip_config(
    payload: SalarySlipConfigUpdate,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Update the salary slip template configuration."""
    config = await _get_or_create_slip_config(session)

    config.company_name = payload.company_name
    config.company_address = payload.company_address
    config.company_phone = payload.company_phone
    config.extra_earnings = [e.model_dump() for e in payload.extra_earnings]
    config.extra_deductions = [d.model_dump() for d in payload.extra_deductions]
    config.footer_note = payload.footer_note

    await session.commit()
    await session.refresh(config)

    return SalarySlipConfigResponse(
        company_name=config.company_name,
        company_address=config.company_address or "",
        company_phone=config.company_phone or "",
        extra_earnings=[SlipItemSchema(**e) for e in (config.extra_earnings or [])],
        extra_deductions=[SlipItemSchema(**d) for d in (config.extra_deductions or [])],
        footer_note=config.footer_note or "",
    )


# ── PDF Generation & Download ────────────────────────────────

async def _build_slip_data(
    session: AsyncSession,
    employee: Employee,
    target_month: str,
    extra_earnings: list | None = None,
    extra_deductions: list | None = None,
    note: str = "",
) -> SalarySlipData:
    """Build SalarySlipData for an employee."""
    policy = await get_or_create_policy(session)
    stats = await calculate_employee_month_stats(session, employee.id, target_month, policy)
    base_salary = round(stats.worked_hours * policy.hourly_wage, 2)

    config = await _get_or_create_slip_config(session)

    # Use provided extras or fall back to template defaults
    earnings = extra_earnings if extra_earnings is not None else [
        SlipItem(label=e["label"], amount=e["default_amount"])
        for e in (config.extra_earnings or [])
    ]
    deductions = extra_deductions if extra_deductions is not None else [
        SlipItem(label=d["label"], amount=d["default_amount"])
        for d in (config.extra_deductions or [])
    ]

    footer = note or config.footer_note or ""

    return SalarySlipData(
        company_name=config.company_name,
        company_address=config.company_address or "",
        company_phone=config.company_phone or "",
        employee_name=employee.name,
        employee_code=employee.employee_code,
        department=employee.department or "",
        month=target_month,
        worked_days=stats.worked_days,
        worked_hours=stats.worked_hours,
        hourly_wage=float(policy.hourly_wage),
        base_salary=base_salary,
        extra_earnings=earnings,
        extra_deductions=deductions,
        footer_note=footer,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )


@router.get("/employee/{employee_id}/pdf")
async def download_salary_pdf(
    employee_id: int,
    month: str | None = Query(None, description="YYYY-MM"),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Download a salary slip PDF for an employee."""
    target_month = _resolve_month(month)

    result = await session.execute(
        select(Employee).where(and_(Employee.id == employee_id, Employee.is_active == True))
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    slip_data = await _build_slip_data(session, employee, target_month)
    pdf_bytes = generate_salary_slip(slip_data)

    filename = f"phieu_luong_{employee.employee_code}_{target_month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Send Salary Slip via Telegram ─────────────────────────────

@router.post("/send/{employee_id}", response_model=SalarySendResult)
async def send_salary_slip(
    employee_id: int,
    month: str | None = Query(None, description="YYYY-MM"),
    body: SalarySendRequest | None = None,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Generate and send a salary slip PDF to an employee via Telegram."""
    target_month = _resolve_month(month)

    result = await session.execute(
        select(Employee).where(and_(Employee.id == employee_id, Employee.is_active == True))
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not employee.telegram_chat_id:
        return SalarySendResult(
            employee_id=employee.id,
            employee_name=employee.name,
            success=False,
            message="Nhân viên chưa liên kết Telegram",
        )

    if not telegram_notifier.is_enabled:
        return SalarySendResult(
            employee_id=employee.id,
            employee_name=employee.name,
            success=False,
            message="Telegram bot chưa được cấu hình",
        )

    # Build slip data with optional overrides from request body
    extra_earnings = None
    extra_deductions = None
    note = ""
    if body:
        extra_earnings = [SlipItem(label=e.label, amount=e.default_amount) for e in body.extra_earnings] if body.extra_earnings else None
        extra_deductions = [SlipItem(label=d.label, amount=d.default_amount) for d in body.extra_deductions] if body.extra_deductions else None
        note = body.note

    slip_data = await _build_slip_data(
        session, employee, target_month,
        extra_earnings=extra_earnings,
        extra_deductions=extra_deductions,
        note=note,
    )
    pdf_bytes = generate_salary_slip(slip_data)

    filename = f"phieu_luong_{employee.employee_code}_{target_month}.pdf"
    parts = target_month.split("-")
    month_display = f"{parts[1]}/{parts[0]}"

    success = await telegram_notifier.send_document(
        chat_id=employee.telegram_chat_id,
        file_bytes=pdf_bytes,
        filename=filename,
        caption=f"📋 Phiếu lương tháng {month_display}\nNhân viên: {employee.name} ({employee.employee_code})",
    )

    return SalarySendResult(
        employee_id=employee.id,
        employee_name=employee.name,
        success=success,
        message="Đã gửi phiếu lương thành công!" if success else "Gửi thất bại. Kiểm tra Telegram bot.",
    )


@router.post("/send-all", response_model=list[SalarySendResult])
async def send_all_salary_slips(
    month: str | None = Query(None, description="YYYY-MM"),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Send salary slips to all employees with linked Telegram accounts."""
    target_month = _resolve_month(month)

    if not telegram_notifier.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram bot chưa được cấu hình")

    result = await session.execute(
        select(Employee)
        .where(and_(
            Employee.is_active == True,
            Employee.telegram_chat_id.isnot(None),
            Employee.telegram_chat_id != "",
        ))
        .order_by(Employee.name.asc())
    )
    employees = result.scalars().all()

    results: list[SalarySendResult] = []
    for employee in employees:
        slip_data = await _build_slip_data(session, employee, target_month)
        pdf_bytes = generate_salary_slip(slip_data)

        filename = f"phieu_luong_{employee.employee_code}_{target_month}.pdf"
        parts = target_month.split("-")
        month_display = f"{parts[1]}/{parts[0]}"

        success = await telegram_notifier.send_document(
            chat_id=employee.telegram_chat_id,
            file_bytes=pdf_bytes,
            filename=filename,
            caption=f"📋 Phiếu lương tháng {month_display}\nNhân viên: {employee.name} ({employee.employee_code})",
        )

        results.append(SalarySendResult(
            employee_id=employee.id,
            employee_name=employee.name,
            success=success,
            message="Đã gửi" if success else "Gửi thất bại",
        ))

    return results
