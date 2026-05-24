"""
IDVision — Attendance Policy Router
Admin endpoints to manage attendance time rules and payroll parameters.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from routers.auth import verify_admin_token
from schemas import AttendancePolicyResponse, AttendancePolicyUpdate
from services.payroll import (
    get_or_create_policy,
    policy_to_response,
    update_policy_from_payload,
)
router = APIRouter(prefix="/api/admin/policy", tags=["Admin Policy"])
@router.get("", response_model=AttendancePolicyResponse)
async def get_policy(
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    policy = await get_or_create_policy(session)
    return AttendancePolicyResponse(**policy_to_response(policy))
@router.put("", response_model=AttendancePolicyResponse)
async def update_policy(
    data: AttendancePolicyUpdate,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    policy = await get_or_create_policy(session)
    update_policy_from_payload(policy, data.model_dump())
    await session.flush()
    await session.refresh(policy)
    return AttendancePolicyResponse(**policy_to_response(policy))
