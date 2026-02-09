"""
Tests for frontend pages.
"""
import pytest


class TestFrontendPages:
    """Tests for frontend HTML pages."""

    def test_feed_page(self, db_session, client_factory):
        """Test the main feed page."""
        client = client_factory(db_session)
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "OpenX" in response.text
        assert "Feed" in response.text

    def test_login_page(self, db_session, client_factory):
        """Test the login page."""
        client = client_factory(db_session)
        response = client.get("/login")

        assert response.status_code == 200
        assert "Login" in response.text
        assert "Secret Key" in response.text

    def test_register_page(self, db_session, client_factory):
        """Test the registration page."""
        client = client_factory(db_session)
        response = client.get("/register")

        assert response.status_code == 200
        assert "Create Account" in response.text
        assert "Username" in response.text

    def test_branch_page(self, db_session, client_factory, test_branch_data):
        """Test branch page."""
        client = client_factory(db_session)
        response = client.get(f"/b/{test_branch_data['name']}")

        assert response.status_code == 200
        assert test_branch_data["name"] in response.text

    def test_branch_page_not_found(self, db_session, client_factory):
        """Test non-existent branch returns 404."""
        client = client_factory(db_session)
        response = client.get("/b/nonexistent")

        assert response.status_code == 404

    def test_user_page(self, db_session, client_factory, test_user_data):
        """Test user profile page."""
        client = client_factory(db_session)
        response = client.get(f"/u/{test_user_data['username']}")

        assert response.status_code == 200
        assert test_user_data["username"] in response.text

    def test_submit_page_unauthenticated(self, db_session, client_factory):
        """Test submit page redirects when not logged in."""
        client = client_factory(db_session)
        response = client.get("/submit", follow_redirects=False)

        assert response.status_code in [302, 307]

    def test_submit_page_authenticated(self, db_session, client_factory, test_user_data):
        """Test submit page when logged in."""
        client = client_factory(db_session)
        client.cookies.set("secret_key", test_user_data["sk"])

        response = client.get("/submit")

        assert response.status_code == 200
        assert "Create Post" in response.text

    def test_create_branch_page_unauthenticated(self, db_session, client_factory):
        """Test create branch page redirects when not logged in."""
        client = client_factory(db_session)
        response = client.get("/create-branch", follow_redirects=False)

        assert response.status_code in [302, 307]


class TestStaticFiles:
    """Tests for static file serving."""

    def test_css_file(self, db_session, client_factory):
        """Test CSS file is served."""
        client = client_factory(db_session)
        response = client.get("/static/css/style.css")

        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_js_file(self, db_session, client_factory):
        """Test JavaScript file is served."""
        client = client_factory(db_session)
        response = client.get("/static/js/app.js")

        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"] or "text/plain" in response.headers["content-type"]

    def test_nonexistent_static_file(self, db_session, client_factory):
        """Test non-existent static file returns 404."""
        client = client_factory(db_session)
        response = client.get("/static/nonexistent.css")

        assert response.status_code == 404
