from sanic import Sanic, response
from sanic_ext import Extend
from markdown import markdown
from sanic.request import Request
from sanic.response import redirect, html, text
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os, aiofiles, base64, json, sqlite3, random, string

app = Sanic("edutec")
Extend(app)

env = Environment(loader=FileSystemLoader("templates"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.static('/uploads', './uploads')

DB_PATH = "edutec.db"

def get_db():
    # Öffne DB-Verbindung mit Row-Zugriff per Namen
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_db():
    # Erstelle Tabellen, falls nicht vorhanden
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            key TEXT NOT NULL
        )
    """)

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

    # Füge Standardautor hinzu
    cursor.execute("SELECT COUNT(*) FROM authors")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO authors (name, key)
            VALUES (?, ?)
        """, [("DerLord", "1510meddl1510")])

    conn.commit()
    conn.close()

# Jinja2-Setup
template_dir = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

@app.route("/")
async def index(request):
    # Lade letzte und ältere Posts
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""... LIMIT 3""")
    rPosts = cursor.fetchall()

    cursor.execute("""...""")
    aPosts = cursor.fetchall()
    conn.close()

    recent_posts = [{...} for row in rPosts]
    all_posts = [{...} for row in (aPosts[3:] if len(aPosts) > 3 else aPosts)]

    template = env.get_template("index.html")
    return html(template.render(recent_posts=recent_posts, all_posts=all_posts))

@app.route("/search")
async def search(request):
    q = request.args.get("q")
    if not q:
        return text("Missing query", status=400)

    try:
        # Decode base64-Suchstring
        padded = q + '=' * (-len(q) % 4)
        query_obj = json.loads(base64.b64decode(padded).decode('utf-8'))

        # Baue SQL-Abfrage
        query_parts, params = [], []

        if query_obj.get("text"):
            query_parts.append("posts.title LIKE ? OR posts.content LIKE ?")
            params += [f"%{query_obj['text']}%"] * 2

        if query_obj.get("topics"):
            query_parts.append("posts.topics LIKE ?")
            params.append(f"%{','.join(query_obj['topics'])}%")

        if query_obj.get("authors"):
            query_parts.append("authors.name LIKE ?")
            params.append(f"%{'% OR authors.name LIKE %'.join(query_obj['authors'])}%")

        sql_query = """SELECT ... FROM posts JOIN authors ON ..."""
        if query_parts:
            sql_query += " WHERE " + " OR ".join(query_parts)
        sql_query += " ORDER BY posts.id DESC"

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        posts = cursor.fetchall()
        conn.close()

        results = [{...} for row in posts]
        template = env.get_template("search.html")
        return html(template.render(query=query_obj, posts=results))

    except Exception as e:
        return text(f"Error decoding query: {e}", status=400)

@app.route("/post/<post_id>")
async def post_view(request, post_id):
    # Lade einzelnen Post
    db = get_db()
    cur = db.execute("SELECT p.*, a.name as author FROM ... WHERE p.id = ?", (post_id,))
    post = cur.fetchone()
    db.close()

    if not post:
        return text("Post not found", status=404)

    template = env.get_template("post.html")
    lang = "clike" if post["code_language"] == "cpp" else post["code_language"]
    return html(template.render(post=post, lang=lang, topics=post["topics"].split(",")))

@app.route("/upload", methods=["GET"])
async def upload_page(request):
    # Upload-Form anzeigen
    template = env.get_template("upload.html")
    return response.html(template.render())

def randomword(length):
    # Zufälliges Wort erzeugen
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

@app.route("/auth", methods=["POST"])
async def auth_post(request: Request):
    form = request.form
    files = request.files

    # Autor identifizieren
    key = form.get("author_key")
    db = get_db()
    cur = db.execute("SELECT id FROM authors WHERE key = ?", (key,))
    author = cur.fetchone()

    if not author:
        return text("Unauthorized", status=403)

    author_id = author["id"]

    # Medien speichern
    video_file, image_file = files.get("video_file"), files.get("image_file")
    video_path = image_path = ""

    if video_file:
        video_path = os.path.join(UPLOAD_DIR, f"vid_{randomword(10)}.{video_file.name.split('.')[-1]}")
        async with aiofiles.open(video_path, 'wb') as f:
            await f.write(video_file.body)

    if image_file:
        image_path = os.path.join(UPLOAD_DIR, f"img_{randomword(10)}.{image_file.name.split('.')[-1]}")
        async with aiofiles.open(image_path, 'wb') as f:
            await f.write(image_file.body)

    # Markdown in HTML umwandeln
    html_content = markdown(form.get("content", ""))

    # Post einfügen
    db.execute("""INSERT INTO posts (...) VALUES (?, ?, ..., ?)""", (
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
    form = request.form
    secret_key = form.get("secret_key")
    author_name = form.get("author_name")

    # Geheimschlüssel überprüfen
    if secret_key != "1510meddl1510":
        return text("Unauthorized", status=403)

    if not author_name:
        return text("Name required", status=400)

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM authors WHERE name = ?", (author_name,))
        if cursor.fetchone():
            return text(f"Author '{author_name}' exists", status=409)

        newkey = randomword(20)
        cursor.execute("INSERT INTO authors (name, key) VALUES (?, ?)", (author_name, newkey))
        conn.commit()
        conn.close()

        return text(f"Author {author_name} created!\nKey: {newkey}\n", status=201)

    except Exception as e:
        return text(f"Error: {e}", status=500)

if __name__ == "__main__":
    setup_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
