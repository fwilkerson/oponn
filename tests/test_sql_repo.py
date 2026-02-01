import pytest
import pytest_asyncio
import secrets
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.repositories.models import Base
from src.repositories.sql_ballot_repository import SqlBallotRepository
from src.services.crypto_service import CryptoService
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
async def db_session(db_url: str, setup_database):
    engine = create_async_engine(db_url)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def repository(db_session: AsyncSession):
    return SqlBallotRepository(db_session)


@pytest.fixture
def crypto():
    return CryptoService()


async def test_create_and_get_ballot(
    repository: SqlBallotRepository, crypto: CryptoService
):
    ballot_id = secrets.token_urlsafe(16)
    keyset = crypto.generate_ballot_keyset()
    enc_dek = crypto.encrypt_ballot_keyset(keyset, ballot_id)
    enc_measure = crypto.encrypt_string("SQL Test", keyset, context="measure")
    enc_options = [crypto.encrypt_string("Yes", keyset, context="option")]

    table = await repository.create_ballot_record(
        ballot_id=ballot_id,
        encrypted_measure=enc_measure,
        encrypted_dek=enc_dek,
        options=enc_options,
        allow_write_in=True,
        start_time=None,
        end_time=None,
    )
    assert table.id == ballot_id
    assert table.encrypted_measure == enc_measure

    fetched = await repository.get_by_id(ballot_id)
    assert fetched is not None
    assert fetched.encrypted_measure == enc_measure


async def test_list_all(repository: SqlBallotRepository, crypto: CryptoService):
    ballot_id = secrets.token_urlsafe(16)
    keyset = crypto.generate_ballot_keyset()
    enc_dek = crypto.encrypt_ballot_keyset(keyset, ballot_id)

    await repository.create_ballot_record(
        ballot_id=ballot_id,
        encrypted_measure=crypto.encrypt_string("Ballot 1", keyset, context="measure"),
        encrypted_dek=enc_dek,
        options=[],
        allow_write_in=False,
        start_time=None,
        end_time=None,
    )

    ballots = await repository.list_all()
    assert len(ballots) >= 1
    assert any(b.id == ballot_id for b in ballots)


async def test_add_vote_and_tally(
    repository: SqlBallotRepository, crypto: CryptoService
):
    ballot_id = secrets.token_urlsafe(16)
    keyset = crypto.generate_ballot_keyset()
    enc_dek = crypto.encrypt_ballot_keyset(keyset, ballot_id)

    table = await repository.create_ballot_record(
        ballot_id=ballot_id,
        encrypted_measure=crypto.encrypt_string("Vote Test", keyset, context="measure"),
        encrypted_dek=enc_dek,
        options=[crypto.encrypt_string("Opt 1", keyset, context="option")],
        allow_write_in=True,
        start_time=None,
        end_time=None,
    )
    opt_1_id = table.options[0].id

    await repository.add_vote(ballot_id, opt_1_id)

    # Add write-in
    enc_write_in = crypto.encrypt_string("My Write-in", keyset, context="option")
    write_in_id = await repository.add_write_in_option(ballot_id, enc_write_in)
    await repository.add_vote(ballot_id, write_in_id)

    tallies = await repository.get_tallies(ballot_id)
    tally_dict = {oid: count for oid, count in tallies}

    assert tally_dict[opt_1_id] == 1
    assert tally_dict[write_in_id] == 1
