from sanic import Sanic, response
from sanic_ext import Extend
from markdown import markdown
from sanic.request import Request
from sanic.response import redirect
from sanic.response import html, text
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import aiofiles
import base64
import json
import sqlite3
import random, string


app = Sanic("edutec")
Extend(app)

env = Environment(loader=FileSystemLoader("templates"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.static('/uploads', './uploads')

DB_PATH = "edutec.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # To access columns by name
    return conn

def setup_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create authors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            key TEXT NOT NULL
        )
    """)

    # Create posts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            icon TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            topics TEXT,
            summary TEXT NOT NULL,
            video_url TEXT,
            video_description TEXT,
            image_url TEXT,
            image_description TEXT,
            content TEXT,
            code_example TEXT,
            code_language TEXT,
            FOREIGN KEY (author_id) REFERENCES authors(id)
        )
    """)

    # Insert sample authors if not already there
    cursor.execute("SELECT COUNT(*) FROM authors")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO authors (name, key)
            VALUES (?, ?)
        """, [
            ("DerLord", "1510meddl1510"),
        ])

    conn.commit()
    conn.close()


# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

@app.route("/")
async def index(request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT posts.id, posts.title, posts.icon, posts.content, posts.date, posts.topics, posts.summary, authors.name as author
        FROM posts
        JOIN authors ON posts.author_id = authors.id
        ORDER BY posts.id DESC
        LIMIT 3
    """)
    rPosts = cursor.fetchall()

    cursor.execute("""
        SELECT posts.id, posts.title, posts.icon, posts.content, posts.date, posts.topics, posts.summary, authors.name as author
        FROM posts
        JOIN authors ON posts.author_id = authors.id
        ORDER BY posts.id DESC
    """)
    aPosts = cursor.fetchall()
    conn.close()

    # Format posts as dicts
    recent_posts = [
        {
            "id": row["id"],
            "title": row["title"],
            "summary": row["summary"],
            "date": row["date"],
            "topic": row["topics"].split(",")[0] if row["topics"] else "",
            "author": row["author"],
            "icon": row["icon"]
        }
        for row in rPosts
    ]

    all_posts = [
        {
            "id": row["id"],
            "title": row["title"],
            "summary": row["summary"],
            "date": row["date"],
            "topic": row["topics"].split(",")[0] if row["topics"] else "",
            "author": row["author"],
            "icon": row["icon"]
        }
        for row in (aPosts[3:] if len(aPosts) > 3 else aPosts) 
    ]

    template = env.get_template("index.html")
    return html(template.render(recent_posts=recent_posts, all_posts=all_posts))


@app.route("/search")
async def search(request):
    q = request.args.get("q")
    if not q:
        return text("Missing query", status=400)

    try:
        # Pad base64 if needed (length must be multiple of 4)
        padded = q + '=' * (-len(q) % 4)
        decoded_bytes = base64.b64decode(padded)
        decoded_json = decoded_bytes.decode('utf-8')
        query_obj = json.loads(decoded_json)
        print("Search Query Object:", query_obj)

        # Construct dynamic SQL based on search query (title, topics, or author)
        query_parts = []
        params = []

        if query_obj.get("text"):
            query_parts.append("posts.title LIKE ? OR posts.content LIKE ?")
            params.extend([f"%{query_obj['text']}%", f"%{query_obj['text']}%"])

        if query_obj.get("topics"):
            query_parts.append("posts.topics LIKE ?")
            params.append(f"%{','.join(query_obj['topics'])}%")

        if query_obj.get("authors"):
            query_parts.append("authors.name LIKE ?")
            params.append(f"%{'% OR authors.name LIKE %'.join(query_obj['authors'])}%")

        # Construct full SQL query
        sql_query = """
            SELECT posts.id, posts.title, posts.icon, posts.content, posts.date, posts.topics, posts.summary, authors.name as author
            FROM posts
            JOIN authors ON posts.author_id = authors.id
        """
        
        if query_parts:
            sql_query += " WHERE " + " OR ".join(query_parts)

        sql_query += " ORDER BY posts.id DESC"

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        posts = cursor.fetchall()
        conn.close()

        # Format posts as dicts
        search_results = [
            {
                "id": row["id"],
                "title": row["title"],
                "summary": row["summary"],
                "date": row["date"],
                "topic": row["topics"].split(",")[0] if row["topics"] else "",
                "author": row["author"],
                "icon": row["icon"]  # Optional icon logic
            }
            for row in posts
        ]

        template = env.get_template("search.html")
        return html(template.render(query=query_obj, posts=search_results))

    except Exception as e:
        return text(f"Error decoding query: {e}", status=400)


@app.route("/post/<post_id>")
async def post_view(request, post_id):
    db = get_db()
    cur = db.execute("""
        SELECT p.*, a.name as author 
        FROM posts p
        JOIN authors a ON p.author_id = a.id
        WHERE p.id = ?
    """, (post_id,))
    post = cur.fetchone()
    db.close()

    if not post:
        return text("Post not found", status=404)

    template = env.get_template("post.html")
    lang = post["code_language"]
    if post["code_language"] == "cpp": lang = "clike"
    return html(template.render(post=post, lang=lang, topics=post["topics"].split(",")))

@app.route("/upload", methods=["GET"])
async def upload_page(request):
    template = env.get_template("upload.html")
    return response.html(template.render())

def randomword(length):
   letters = string.ascii_lowercase
   return ''.join(random.choice(letters) for i in range(length))

@app.route("/auth", methods=["POST"])
async def auth_post(request: Request):
    form = request.form
    files = request.files

    # Verify author key
    key = form.get("author_key")
    db = get_db()
    cur = db.execute("SELECT id, name FROM authors WHERE key = ?", (key,))
    author = cur.fetchone()

    if not author:
        return text("Unauthorized: invalid author key", status=403)

    author_id = author["id"]

    # Save files
    UPLOAD_DIR = "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    video_file = files.get("video_file")
    image_file = files.get("image_file")

    video_path = ""
    image_path = ""

    if video_file:
        video_path = os.path.join(UPLOAD_DIR, f"vid_{randomword(10)}.{video_file.name.split('.')[-1]}")
        async with aiofiles.open(video_path, 'wb') as f:
            await f.write(video_file.body)

    if image_file:
        image_path = os.path.join(UPLOAD_DIR, f"img_{randomword(10)}.{image_file.name.split('.')[-1]}")
        async with aiofiles.open(image_path, 'wb') as f:
            await f.write(image_file.body)

    # Convert markdown content to HTML
    markdown_content = form.get("content", "")
    html_content = markdown(markdown_content)

    # Insert post into DB
    db.execute("""
        INSERT INTO posts 
        (title, icon, author_id, date, topics, summary, video_url, video_description, image_url, image_description, content, code_example, code_language)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        form.get("title"),
        form.get("icon"),
        author_id,
        form.get("date"),
        form.get("topics"),
        form.get("summary"),
        os.path.join("/", video_path),
        form.get("video_description"),
        os.path.join("/", image_path),
        form.get("image_description"),
        html_content,
        form.get("code_example"),
        form.get("code_language") or "python"
    ))
    db.commit()
    post_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    return redirect(f"/post/{post_id}")

@app.route("/create_author", methods=["POST"])
async def create_author(request):
    # Extract the secret key from the request body
    form = request.form
    secret_key = form.get("secret_key")
    author_name = form.get("author_name")

    # The predefined secret key (for example purposes)
    SECRET_KEY = "1510meddl1510"  # Replace with your actual secret key

    if secret_key != SECRET_KEY:
        return text("Unauthorized: Invalid secret key", status=403)

    if not author_name:
        return text("Author name is required", status=400)

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if the author already exists
        cursor.execute("SELECT id FROM authors WHERE name = ?", (author_name,))
        existing_author = cursor.fetchone()
        if existing_author:
            return text(f"Author '{author_name}' already exists", status=409)

        newkey = randomword(20)

        cursor.execute("INSERT INTO authors (name, key) VALUES (?, ?)", (author_name, newkey))
        conn.commit()
        conn.close()

        return text(f"Author {author_name} created successfully!\nAuthor Key: {newkey}\n", status=201)

    except Exception as e:
        return text(f"Error creating author: {e}", status=500)


if __name__ == "__main__":
    setup_db()
    app.run(host="0.0.0.0", port=8000, debug=True)