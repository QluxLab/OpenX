"""
Tests for branch endpoints.
"""
import pytest


class TestBranchCreation:
    """Tests for branch creation."""

    def test_create_branch_authenticated(self, db_session, client_factory, test_user_data):
        """Test successful branch creation."""
        client = client_factory(db_session)
        response = client.post(
            "/api/branch/create",
            json={
                "name": "newbranch",
                "description": "A new test branch"
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "newbranch"
        assert data["description"] == "A new test branch"
        assert data["created_by"] == test_user_data["username"]
        assert "master_key" in data
        assert data["master_key"].startswith("bmk-")

    def test_create_branch_unauthenticated(self, db_session, client_factory):
        """Test that unauthenticated requests are rejected."""
        client = client_factory(db_session)
        response = client.post(
            "/api/branch/create",
            json={"name": "newbranch"}
        )

        assert response.status_code == 422  # Missing header

    def test_create_duplicate_branch(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test that duplicate branch names are rejected."""
        client = client_factory(db_session)
        response = client.post(
            "/api/branch/create",
            json={"name": test_branch_data["name"]},
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert response.status_code == 409

    def test_create_branch_invalid_name(self, db_session, client_factory, test_user_data):
        """Test that invalid branch names are rejected."""
        client = client_factory(db_session)
        response = client.post(
            "/api/branch/create",
            json={"name": "invalid name!"},
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert response.status_code == 422


class TestBranchRetrieval:
    """Tests for branch retrieval."""

    def test_get_branch_info(self, db_session, client_factory, test_branch_data):
        """Test getting branch information."""
        client = client_factory(db_session)
        response = client.get(f"/api/branch/{test_branch_data['name']}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_branch_data["name"]
        assert data["description"] == test_branch_data["description"]
        # Master key should not be exposed
        assert "master_key" not in data

    def test_get_nonexistent_branch(self, db_session, client_factory):
        """Test getting a non-existent branch."""
        client = client_factory(db_session)
        response = client.get("/api/branch/nonexistent")

        assert response.status_code == 404


class TestBranchPosts:
    """Tests for branch posts."""

    def test_create_text_post(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test creating a text post in a branch."""
        client = client_factory(db_session)
        response = client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "text",
                "content": "Hello, world!",
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "text"
        assert data["content"] == "Hello, world!"
        assert data["branch"] == test_branch_data["name"]

    def test_create_image_post(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test creating an image post in a branch."""
        client = client_factory(db_session)
        response = client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "image",
                "content": "Check out this image",
                "image_url": "http://example.com/image.png",
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "image"
        assert data["image_url"] == "http://example.com/image.png"

    def test_create_video_post(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test creating a video post in a branch."""
        client = client_factory(db_session)
        response = client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "video",
                "content": "Check out this video",
                "video_url": "http://example.com/video.mp4",
                "duration_seconds": 120,
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "video"
        assert data["video_url"] == "http://example.com/video.mp4"
        assert data["duration_seconds"] == 120

    def test_get_branch_posts(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test getting posts from a branch."""
        client = client_factory(db_session)

        # Create a post first
        client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "text",
                "content": "Test post content",
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        response = client.get(f"/api/branch/{test_branch_data['name']}/posts")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(p["content"] == "Test post content" for p in data)

    def test_delete_own_post(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test deleting own post."""
        client = client_factory(db_session)

        # Create a post to delete
        response = client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "text",
                "content": "Post to delete",
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )
        post_id = response.json()["id"]

        # Delete the post
        delete_response = client.delete(
            f"/api/branch/{test_branch_data['name']}/posts/{post_id}",
            headers={"X-Secret-Key": test_user_data["sk"]}
        )

        assert delete_response.status_code == 204


class TestBranchModeration:
    """Tests for branch moderation."""

    def test_moderate_delete_post(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test moderator deleting any post."""
        client = client_factory(db_session)

        # Create a post
        response = client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "text",
                "content": "Post to moderate",
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )
        post_id = response.json()["id"]

        # Delete as moderator
        response = client.delete(
            f"/api/branch/{test_branch_data['name']}/moderate/posts/{post_id}",
            headers={"X-Branch-Master-Key": test_branch_data["master_key"]}
        )

        assert response.status_code == 204

    def test_moderate_without_master_key(self, db_session, client_factory, test_user_data, test_branch_data):
        """Test that moderation requires master key."""
        client = client_factory(db_session)

        # Create a post
        response = client.post(
            f"/api/branch/{test_branch_data['name']}/posts",
            json={
                "type": "text",
                "content": "Post to moderate",
                "to_branch": test_branch_data["name"]
            },
            headers={"X-Secret-Key": test_user_data["sk"]}
        )
        post_id = response.json()["id"]

        # Try to delete with invalid master key
        response = client.delete(
            f"/api/branch/{test_branch_data['name']}/moderate/posts/{post_id}",
            headers={"X-Branch-Master-Key": "bmk-invalidkey"}
        )

        assert response.status_code == 403
