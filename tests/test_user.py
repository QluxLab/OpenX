"""
Tests for user endpoints.
"""

import pytest


class TestUserPosts:
    """Tests for user post endpoints."""

    def test_create_user_post(self, db_session, client_factory, test_user_data):
        """Test creating a post on user profile."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])
        response = client.post(
            "/api/user/posts/",
            json={"type": "text", "content": "My profile post", "to_branch": None},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "My profile post"
        assert data["branch"] is None

    def test_create_post_to_branch(
        self, db_session, client_factory, test_user_data, test_branch_data
    ):
        """Test creating a post to a specific branch."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])
        response = client.post(
            "/api/user/posts/",
            json={
                "type": "text",
                "content": "Branch post",
                "to_branch": test_branch_data["name"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["branch"] == test_branch_data["name"]

    def test_get_user_posts(self, db_session, client_factory, test_user_data):
        """Test getting user's posts."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])

        # Create a post first
        client.post(
            "/api/user/posts/",
            json={"type": "text", "content": "User's post", "to_branch": None},
        )

        # Get posts
        response = client.get(f"/api/user/{test_user_data['username']}/posts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(p["content"] == "User's post" for p in data)

    def test_get_user_posts_exclude_branch(
        self, db_session, client_factory, test_user_data, test_branch_data
    ):
        """Test that branch posts are excluded by default."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])

        # Create profile post
        client.post(
            "/api/user/posts/",
            json={"type": "text", "content": "Profile post", "to_branch": None},
        )

        # Create branch post
        client.post(
            "/api/user/posts/",
            json={
                "type": "text",
                "content": "Branch post",
                "to_branch": test_branch_data["name"],
            },
        )

        # Get profile posts only (default)
        response = client.get(
            f"/api/user/{test_user_data['username']}/posts/",
            params={"include_branch_posts": False},
        )

        assert response.status_code == 200
        data = response.json()
        # All returned posts should have branch as None
        for post in data:
            assert post["branch"] is None

    def test_get_post_by_id(self, db_session, client_factory, test_user_data):
        """Test getting a single post by ID."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])

        # Create a post
        create_response = client.post(
            "/api/user/posts/",
            json={"type": "text", "content": "Single post", "to_branch": None},
        )
        post_id = create_response.json()["id"]

        # Get the post
        response = client.get(f"/api/user/posts/{post_id}/")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == post_id
        assert data["content"] == "Single post"

    def test_delete_own_post(self, db_session, client_factory, test_user_data):
        """Test deleting own post."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])

        # Create a post
        create_response = client.post(
            "/api/user/posts/",
            json={"type": "text", "content": "To delete", "to_branch": None},
        )
        post_id = create_response.json()["id"]

        # Delete the post
        delete_response = client.delete(f"/api/user/posts/{post_id}/")

        assert delete_response.status_code == 204

        # Verify it's deleted
        get_response = client.get(f"/api/user/posts/{post_id}/")
        assert get_response.status_code == 404

    def test_update_post(self, db_session, client_factory, test_user_data):
        """Test updating a post."""
        client = client_factory(db_session, user_sk=test_user_data["sk"])

        # Create a post
        create_response = client.post(
            "/api/user/posts/",
            json={"type": "text", "content": "Original content", "to_branch": None},
        )
        post_id = create_response.json()["id"]

        # Update the post
        update_response = client.patch(
            f"/api/user/posts/{post_id}/", json={"content": "Updated content"}
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["content"] == "Updated content"
