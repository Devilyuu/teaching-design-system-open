from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models import User
from app.schemas import WorkbenchStatusRead
from app.services.workbench_import import WorkbenchError, owned_by, workbench_from_env


router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/workbench", response_model=WorkbenchStatusRead)
def workbench_status(current_user: User = Depends(get_current_user)) -> dict:
    """Whether this teacher's own workbench is wired up on this deployment.

    The interface asks before offering the button, and the answer is per
    teacher: the pilot puts everyone on one deployment, so a button shown to
    all of them would file their work into whoever's workbench is configured.

    A partial configuration is reported rather than hidden -- that is an
    operations mistake, and silently disabling the feature buries it.
    """
    try:
        workbench = workbench_from_env()
    except WorkbenchError as exc:
        return {"configured": False, "message": str(exc)}
    return {"configured": owned_by(workbench, current_user.employee_no), "message": ""}
