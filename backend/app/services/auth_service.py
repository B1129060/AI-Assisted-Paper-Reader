from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User


def get_or_create_dev_user(db: Session) -> User:
    """
    Temporary development identity used before the school SSO bridge is connected.

    This lets the backend be refactored to support users and ownership checks now.
    Later, replace get_current_user() with the real JWT / school-login based user.
    """
    user = db.query(User).filter(User.school_user_oid == settings.DEV_USER_OID).first()
    if user:
        updated = False
        if user.email != settings.DEV_USER_EMAIL:
            user.email = settings.DEV_USER_EMAIL
            updated = True
        if user.name != settings.DEV_USER_NAME:
            user.name = settings.DEV_USER_NAME
            updated = True
        if user.tenant_id != settings.DEV_TENANT_ID:
            user.tenant_id = settings.DEV_TENANT_ID
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
        return user

    user = User(
        school_user_oid=settings.DEV_USER_OID,
        email=settings.DEV_USER_EMAIL,
        name=settings.DEV_USER_NAME,
        tenant_id=settings.DEV_TENANT_ID,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to initialize development user: {exc}")


def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Temporary current-user dependency.

    During development this always returns the same dev user. After the school SSO
    URL/callback issue is solved, this function should validate your own session/JWT
    and return the real logged-in user instead.
    """
    return get_or_create_dev_user(db)
