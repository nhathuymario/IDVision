"""
IDVision — Employee Router
CRUD endpoints for employee management.
"""

import logging
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Employee
from schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/employees", tags=["Employees"])


def _to_response(emp: Employee) -> EmployeeResponse:
    """Convert Employee ORM model to response schema."""
    return EmployeeResponse(
        id=emp.id,
        name=emp.name,
        employee_code=emp.employee_code,
        department=emp.department,
        telegram_chat_id=emp.telegram_chat_id,
        has_password=emp.password_hash is not None,
        is_enrolled=emp.face_encoding is not None,
        enrolled_at=emp.enrolled_at,
        is_active=emp.is_active,
        created_at=emp.created_at,
    )


@router.post("", response_model=EmployeeResponse, status_code=201)
async def create_employee(
    data: EmployeeCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new employee."""
    # Check for duplicate employee_code
    existing = await session.execute(
        select(Employee).where(Employee.employee_code == data.employee_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Employee code '{data.employee_code}' already exists."
        )

    employee = Employee(
        name=data.name,
        employee_code=data.employee_code,
        department=data.department,
        telegram_chat_id=data.telegram_chat_id,
    )

    # Hash password if provided
    if data.password:
        employee.password_hash = bcrypt.hashpw(
            data.password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
    session.add(employee)
    await session.flush()
    await session.refresh(employee)

    logger.info(f"Created employee: {employee.name} (code={employee.employee_code})")
    return _to_response(employee)


@router.get("", response_model=EmployeeListResponse)
async def list_employees(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    active_only: bool = Query(True),
    search: Optional[str] = Query(None, description="Search by name or code"),
    session: AsyncSession = Depends(get_db),
):
    """List employees with optional filtering and pagination."""
    query = select(Employee)
    count_query = select(func.count(Employee.id))

    if active_only:
        query = query.where(Employee.is_active == True)
        count_query = count_query.where(Employee.is_active == True)

    if search:
        search_filter = (
            Employee.name.ilike(f"%{search}%") |
            Employee.employee_code.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    result = await session.execute(
        query.order_by(Employee.id).offset(skip).limit(limit)
    )
    employees = result.scalars().all()

    return EmployeeListResponse(
        total=total,
        employees=[_to_response(emp) for emp in employees],
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Get employee details by ID."""
    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return _to_response(employee)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update employee information."""
    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)

    # Handle password separately (hash it)
    if "password" in update_data:
        pwd = update_data.pop("password")
        if pwd:
            employee.password_hash = bcrypt.hashpw(
                pwd.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

    for field, value in update_data.items():
        setattr(employee, field, value)

    await session.flush()
    await session.refresh(employee)

    logger.info(f"Updated employee: {employee.name} (id={employee.id})")
    return _to_response(employee)


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Soft delete employee (set is_active=False)."""
    result = await session.execute(
        select(Employee).where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    employee.is_active = False
    await session.flush()

    # Remove from face cache
    from services.face_cache import face_cache
    face_cache.remove(employee_id)

    logger.info(f"Deactivated employee: {employee.name} (id={employee.id})")
    return {"message": f"Employee '{employee.name}' has been deactivated."}
