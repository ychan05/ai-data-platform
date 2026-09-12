from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import create_engine

from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.datasource import DataSourceCreate
from app.core.security import encrypt_value, decrypt_value
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_sync_url(ds: DataSource, plain_password: str) -> str:
    """构造同步连接 URL（用于测试连接和 Schema 自省）。"""
    driver = {"postgresql": "postgresql+psycopg2", "mysql": "mysql+pymysql"}
    prefix = driver.get(ds.db_type, ds.db_type)
    return f"{prefix}://{ds.username}:{plain_password}@{ds.host}:{ds.port}/{ds.database_name}"


async def create_datasource(
    db: AsyncSession, user: User, req: DataSourceCreate
) -> DataSource:
    ds = DataSource(
        user_id=user.id,
        name=req.name,
        db_type=req.db_type,
        host=req.host,
        port=req.port,
        database_name=req.database_name,
        username=req.username,
        encrypted_password=encrypt_value(req.password),
    )
    db.add(ds)
    await db.flush()

    logger.info("datasource.created", datasource_id=ds.id, user_id=user.id, db_type=ds.db_type)
    return ds


async def list_datasources(
    db: AsyncSession, user: User, skip: int = 0, limit: int = 20
) -> tuple[list[DataSource], int]:
    # 查询总数
    count_stmt = select(func.count()).select_from(DataSource).where(
        DataSource.user_id == user.id,
        DataSource.is_active == True,
    )
    total = (await db.execute(count_stmt)).scalar()

    # 查询列表
    stmt = (
        select(DataSource)
        .where(DataSource.user_id == user.id, DataSource.is_active == True)
        .order_by(DataSource.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def get_datasource(db: AsyncSession, user: User, datasource_id: int) -> DataSource:
    stmt = select(DataSource).where(
        DataSource.id == datasource_id,
        DataSource.user_id == user.id,
        DataSource.is_active == True,
    )
    result = await db.execute(stmt)
    ds = result.scalar_one_or_none()
    if not ds:
        raise NotFoundError("数据源", datasource_id)
    return ds


async def delete_datasource(db: AsyncSession, user: User, datasource_id: int) -> None:
    ds = await get_datasource(db, user, datasource_id)
    ds.is_active = False
    await db.flush()
    logger.info("datasource.deleted", datasource_id=ds.id, user_id=user.id)


async def test_connection(db: AsyncSession, user: User, datasource_id: int) -> tuple[bool, str]:
    ds = await get_datasource(db, user, datasource_id)
    plain_password = decrypt_value(ds.encrypted_password)
    url = _build_sync_url(ds, plain_password)

    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True, "连接成功"
    except Exception as e:
        logger.warning("datasource.connection_failed", datasource_id=ds.id, error=str(e))
        return False, f"连接失败:{str(e)}"