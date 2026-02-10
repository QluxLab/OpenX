"""
RSS feed endpoints for OpenX.

Provides RSS 2.0 feeds for:
- Global feed: /feed.rss
- Branch feeds: /b/<branch>.rss
- User feeds: /u/<username>.rss
"""
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from src.core.db.session import get_db
from src.core.db.tables.userpost import UserPost
from src.core.db.tables.branch import Branch

router = APIRouter(tags=["rss"])


def escape_xml(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_rfc822(dt: datetime) -> str:
    """Format datetime as RFC 822 for RSS pubDate."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_rss_xml(
    title: str,
    link: str,
    description: str,
    posts: list[UserPost],
    feed_url: str,
) -> str:
    """
    Build RSS 2.0 XML from posts.
    """
    rss = Element("rss", version="2.0", attrib={
        "xmlns:atom": "http://www.w3.org/2005/Atom"
    })
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = title
    SubElement(channel, "link").text = link
    SubElement(channel, "description").text = description
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "generator").text = "OpenX RSS Generator"
    SubElement(channel, "lastBuildDate").text = format_rfc822(datetime.now(timezone.utc))

    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", feed_url)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for post in posts:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = post.title or "Untitled"

        post_link = f"{link.rstrip('/')}/post/{post.id}"
        SubElement(item, "link").text = post_link

        guid = SubElement(item, "guid")
        guid.text = post_link
        guid.set("isPermaLink", "true")

        content = post.content or ""
        if len(content) > 1000:
            content = content[:997] + "..."
        SubElement(item, "description").text = escape_xml(content)

        SubElement(item, "author").text = post.username

        if post.branch:
            SubElement(item, "category").text = post.branch

        pub_date = post.created_at or datetime.now(timezone.utc)
        SubElement(item, "pubDate").text = format_rfc822(pub_date)

    xml_str = tostring(rss, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ", encoding=None)


@router.get("/feed.rss")
async def global_rss_feed(session: Session = Depends(get_db)):
    """Global RSS feed - all posts from all branches."""
    posts = session.execute(
        select(UserPost)
        .where(UserPost.branch.isnot(None))
        .order_by(desc(UserPost.created_at))
        .limit(50)
    ).scalars().all()

    xml_content = build_rss_xml(
        title="OpenX - Global Feed",
        link="http://localhost:8000",
        description="Latest posts from all branches on OpenX",
        posts=posts,
        feed_url="http://localhost:8000/feed.rss",
    )

    return Response(
        content=xml_content,
        media_type="application/rss+xml; charset=utf-8",
    )


@router.get("/b/{branch_name}.rss")
async def branch_rss_feed(
    branch_name: str,
    session: Session = Depends(get_db),
):
    """RSS feed for a specific branch."""
    branch = session.execute(
        select(Branch).where(
            Branch.name == branch_name,
            Branch.deleted_at.is_(None)
        )
    ).scalar()

    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    posts = session.execute(
        select(UserPost)
        .where(UserPost.branch == branch_name)
        .order_by(desc(UserPost.created_at))
        .limit(50)
    ).scalars().all()

    xml_content = build_rss_xml(
        title=f"b/{branch_name} - OpenX",
        link=f"http://localhost:8000/b/{branch_name}",
        description=branch.description or f"Posts from b/{branch_name}",
        posts=posts,
        feed_url=f"http://localhost:8000/b/{branch_name}.rss",
    )

    return Response(
        content=xml_content,
        media_type="application/rss+xml; charset=utf-8",
    )


@router.get("/u/{username}.rss")
async def user_rss_feed(
    username: str,
    session: Session = Depends(get_db),
):
    """RSS feed for a specific user's posts."""
    posts = session.execute(
        select(UserPost)
        .where(UserPost.username == username)
        .order_by(desc(UserPost.created_at))
        .limit(50)
    ).scalars().all()

    xml_content = build_rss_xml(
        title=f"u/{username} - OpenX",
        link=f"http://localhost:8000/u/{username}",
        description=f"Posts by {username} on OpenX",
        posts=posts,
        feed_url=f"http://localhost:8000/u/{username}.rss",
    )

    return Response(
        content=xml_content,
        media_type="application/rss+xml; charset=utf-8",
    )
