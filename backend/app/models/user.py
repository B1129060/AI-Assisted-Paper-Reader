# Database model for application users mapped from development or school-login identity.

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# Application user row keyed by school or development identity.
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("school_user_oid", name="uq_users_school_user_oid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    school_user_oid = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    name = Column(String, nullable=True)
    tenant_id = Column(String, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    papers = relationship("Paper", back_populates="owner")
