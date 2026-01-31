import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.models.ballot_models import BallotCreate
from src.repositories.models import Base
from src.repositories.sql_ballot_repository import SqlBallotRepository
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def db_url(postgres_container):
    return postgres_container.get_connection_url().replace("psycopg2", "asyncpg")


@pytest_asyncio.fixture(scope="session")
async def setup_database(db_url: str):
    # Run migrations
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session(db_url: str, _):
    engine = create_async_engine(db_url)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def repository(db_session: AsyncSession):
    return SqlBallotRepository(db_session)


@pytest.mark.asyncio
async def test_create_and_get_ballot(repository: SqlBallotRepository):
    bc = BallotCreate(
        measure="SQL Test Ballot", options=["Yes", "No"], allow_write_in=True
    )
    ballot = await repository.create(bc)
    assert ballot.ballot_id is not None
    assert ballot.measure == "SQL Test Ballot"
    assert "Yes" in ballot.options
    assert "No" in ballot.options

    fetched = await repository.get_by_id(ballot.ballot_id)
    assert fetched is not None
    assert fetched.measure == "SQL Test Ballot"


@pytest.mark.asyncio
async def test_list_all(repository: SqlBallotRepository):
    bc = BallotCreate(measure="Ballot 1", options=["A", "B"], allow_write_in=False)
    _ = await repository.create(bc)

    ballots = await repository.list_all()
    assert len(ballots) >= 1
    assert any(b.measure == "Ballot 1" for b in ballots)


@pytest.mark.asyncio
async def test_add_vote_and_tally(repository: SqlBallotRepository):
    bc = BallotCreate(
        measure="Vote Test", options=["Option 1", "Option 2"], allow_write_in=True
    )
    ballot = await repository.create(bc)

    await repository.add_vote(ballot.ballot_id, "Option 1")
    await repository.add_vote(ballot.ballot_id, "Option 1")
    await repository.add_vote(ballot.ballot_id, "Write-in")

    tallies = await repository.get_tallies(ballot.ballot_id)
    tally_dict = {t.option: t.count for t in tallies}

    assert tally_dict["Option 1"] == 2
    assert tally_dict["Option 2"] == 0
    assert tally_dict["Write-in"] == 1
