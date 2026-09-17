from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import create_engine

from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate
from app.core.security import encrypt_value, decrypt_value
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_sync_url(ds: DataSource, plain_password: str) -> str:
    """构造同步连接 URL（用于测试连接和 Schema 自省）。"""
    driver = {"postgresql": "postgresql+psycopg2", "mysql": "mysql+pymysql"}
    prefix = driver.get(ds.db_type, ds.db_type)
    return f"{prefix}://{ds.username}:{plain_password}@{ds.host}:{ds.port}/{ds.database_name}"


def _test_connection_values(
    db_type: str,
    username: str,
    plain_password: str,
    host: str,
    port: int,
    database_name: str,
) -> tuple[bool, str]:
    driver = {"postgresql": "postgresql+psycopg2", "mysql": "mysql+pymysql"}
    prefix = driver.get(db_type, db_type)
    url = f"{prefix}://{username}:{plain_password}@{host}:{port}/{database_name}"
    engine = None
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "连接成功"
    except Exception as e:
        return False, f"连接失败:{str(e)}"
    finally:
        if engine is not None:
            engine.dispose()


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
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[DataSource], int, int | None]:
    # 查询总数
    count_stmt = select(func.count()).select_from(DataSource).where(
        DataSource.user_id == user.id,
        DataSource.is_active == True,
    )
    total = (await db.execute(count_stmt)).scalar()

    # 查询列表
    conditions = [DataSource.user_id == user.id, DataSource.is_active == True]
    if cursor is not None:
        conditions.append(DataSource.id < cursor)

    stmt = (
        select(DataSource)
        .where(*conditions)
        .order_by(DataSource.id.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    next_cursor = items[limit].id if len(items) > limit else None
    items = items[:limit]

    return items, total, next_cursor


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


async def update_datasource(
    db: AsyncSession, user: User, datasource_id: int, req: DataSourceUpdate
) -> DataSource:
    ds = await get_datasource(db, user, datasource_id)
    updates = req.model_dump(exclude_unset=True)
    connection_fields = {"host", "port", "database_name", "username", "password"}

    if connection_fields.intersection(updates):
        plain_password = updates.get("password", decrypt_value(ds.encrypted_password))
        success, message = _test_connection_values(
            ds.db_type,
            updates.get("username", ds.username),
            plain_password,
            updates.get("host", ds.host),
            updates.get("port", ds.port),
            updates.get("database_name", ds.database_name),
        )
        if not success:
            raise ValidationError(message)

    if "password" in updates:
        ds.encrypted_password = encrypt_value(updates.pop("password"))
    for field, value in updates.items():
        setattr(ds, field, value)

    await db.flush()
    logger.info("datasource.updated", datasource_id=ds.id, user_id=user.id)
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