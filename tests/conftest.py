"""
Test configuration and fixtures for OpenX tests.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.core.db.tables.base import Base
from src.core.db.tables.secretkey import SecretKey
from src.core.db.tables.recoverykey import RecoveryKey
from src.core.db.tables.branch import Branch
from src.core.db.tables.userpost import UserPost, TextPost, ImagePost, VideoPost
from src.core.db.tables.media import Media
from src.core.security import hash_key, new_sk, new_rk


@pytest.fixture(scope="function")
def db_session():
    """Create an isolated test database session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client_factory():
    """Factory to create test clients with a specific db session."""
    def create_client(session):
        from src.app import app
        from src.core.db.session import get_db

        def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        return client

    yield create_client

    # Cleanup
    from src.app import app
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data(db_session):
    """Create a test user and return their credentials."""
    sk = new_sk()
    rk = new_rk()

    sk_id = sk[:16]
    rk_id = rk[:16]

    sk_hash = hash_key(sk)
    rk_hash = hash_key(rk)

    secret_key = SecretKey(
        sk_id=sk_id,
        sk_hash=sk_hash,
        username="testuser"
    )
    recovery_key = RecoveryKey(
        rk_id=rk_id,
        rk_hash=rk_hash,
        username="testuser"
    )

    db_session.add(secret_key)
    db_session.add(recovery_key)
    db_session.commit()

    return {
        "username": "testuser",
        "sk": sk,
        "rk": rk
    }


@pytest.fixture
def test_branch_data(db_session, test_user_data):
    """Create a test branch."""
    from src.core.security import hash_master_key, new_branch_master_key

    master_key = new_branch_master_key()
    hashed_key = hash_master_key(master_key)

    branch = Branch(
        name="testbranch",
        description="A test branch",
        master_key=hashed_key,
        created_by=test_user_data["username"]
    )

    db_session.add(branch)
    db_session.commit()

    return {
        "name": "testbranch",
        "description": "A test branch",
        "master_key": master_key,
        "created_by": test_user_data["username"]
    }
