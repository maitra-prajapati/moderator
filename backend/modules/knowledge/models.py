from sqlalchemy import JSON, String, UniqueConstraint, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass



class Brand(Base):

    __tablename__ = "knowledge_brands"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)



class knowledge_version(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (UniqueConstraint("brand_id" , "version_no"),)


    id: Mapped[str] = mapped_column(String(150), primary_key=True)

    brand_id: Mapped[str] = mapped_column(
        String(150), ForeignKey("knowledge_brands.id"),
        index=True, 
        nullable= False
    )

    version_no: Mapped[int] = mapped_column(Integer , nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)


    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    activated_at : Mapped[str | None] = mapped_column(String(40), nullable=True)



