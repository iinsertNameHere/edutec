<h1 style="font-size: 50px"> edutec - Lehrndatenbank </h1>

### 📦 1. Datenbankaufbau

Die App speichert alle Inhalte (Autoren, Posts) in einer **SQLite-Datenbank** (`edutec.db`). Die Struktur ist in **zwei Tabellen** aufgeteilt:

#### `authors` – Tabelle für Benutzer:innen
| Spalte      | Typ     | Bedeutung                     |
|-------------|---------|-------------------------------|
| `id`        | INTEGER | Eindeutige ID (automatisch)   |
| `name`      | TEXT    | Name des Autors               |
| `key`       | TEXT    | Geheimer Upload-Schlüssel     |

#### `posts` – Tabelle für die Wiki-Artikel
| Spalte             | Typ     | Bedeutung                                     |
|--------------------|---------|-----------------------------------------------|
| `id`               | INTEGER | Eindeutige Post-ID (automatisch)              |
| `title`            | TEXT    | Titel des Posts                               |
| `icon`             | TEXT    | Symbol (z. B. ein Emoji)                      |
| `author_id`        | INTEGER | Verknüpfung zum Autor                         |
| `date`             | TEXT    | Veröffentlichungsdatum                        |
| `topics`           | TEXT    | Kommagetrennte Themen (z. B. `#AI,#Python`)   |
| `summary`          | TEXT    | Kurzbeschreibung                              |
| `video_url`        | TEXT    | Pfad zum Video                                |
| `video_description`| TEXT    | Beschreibung des Videos                       |
| `image_url`        | TEXT    | Pfad zum Bild                                 |
| `image_description`| TEXT    | Beschreibung des Bildes                       |
| `content`          | TEXT    | HTML-Inhalt des Posts (aus Markdown generiert)|
| `code_example`     | TEXT    | Beispielcode                                  |
| `code_language`    | TEXT    | Sprache des Beispielcodes (z. B. `python`)    |

👉 Zwischen `posts.author_id` und `authors.id` besteht eine sogenannte **Foreign Key Beziehung**, um klar zu machen, **welcher Autor den Post geschrieben hat.**

---

### 🔗 2. Anbindung mit Python und Sanic

#### 📂 Aufbau

```bash
src/
├── edutec.db              <- Die SQLite-Datenbank
├── uploads/               <- Bilder/Videos von Posts
├── templates/             <- HTML-Dateien (Jinja2 Templates)
├── app.py                <- Die Sanic-App
```

#### 🧩 Setup der Datenbank

```python
def setup_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS authors (...)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS posts (...)""")

    conn.commit()
    conn.close()
```

Das passiert nur **einmal beim Starten**, wenn die Datenbank noch leer ist.

#### 📚 Daten auslesen

Beispiel: Aktuelle Posts für die Startseite holen:

```python
cursor.execute("""
    SELECT posts.title, posts.summary, authors.name
    FROM posts
    JOIN authors ON posts.author_id = authors.id
    ORDER BY posts.id DESC
""")
```

➡ Das ist ein **JOIN**, d. h. es werden `posts` und `authors` zusammengefasst – über die `author_id`.

---

### 🧪 3. SQL (aus dem Code erklärt)

Hier ein paar SQL-Basics anhand der App:

#### 🔍 Abfrage: Suche nach Posts

```sql
SELECT *
FROM posts
WHERE title LIKE '%Python%'
```
➡ `LIKE` bedeutet: finde alle Titel, die `Python` enthalten.

#### 🔗 Verknüpfung: Autor + Post

```sql
SELECT posts.title, authors.name
FROM posts
JOIN authors ON posts.author_id = authors.id
```
➡ Zeigt Titel **und den Autor-Namen** an.

#### ➕ Eintrag erstellen (neuer Post)

```sql
INSERT INTO posts (title, summary, author_id, ...)
VALUES ('Python Grundlagen', 'Was ist Python?', 1, ...)
```

➡ Fügt einen Post hinzu – mit dem Autor `1`.

---

### ✍️ 4. Markdown zu HTML

Beim Hochladen von Inhalten wird das Markdown automatisch in HTML umgewandelt:

```python
from markdown import markdown

html_content = markdown(markdown_text)
```

> **Beispiel Markdown:**

```markdown
# Überschrift
**fett** und *kursiv*
```

> **Wird zu HTML:**

```html
<h1>Überschrift</h1>
<strong>fett</strong> und <em>kursiv</em>
```

In der Datenbank wird **HTML gespeichert**, damit es direkt auf der Webseite angezeigt werden kann.

---

### 🎁 Such-Feature mit Base64

Wenn du auf der Webseite nach `Grundlagen zu #python von @DerLord` suchst, wird die Suchanfrage **als Base64 codiertes json** übergeben.

Beispiel:

```json
{
  "text": "Grundlagen zu von",
  "topics": ["#Python"],
  "authors": ["@DerLord"]
}
```

➡ wird als String codiert → an `/search?q=...` übergeben → auf dem Server wieder decodiert → SQL-Abfrage.

### 📔 Autor hinzufügen
Um einen neuen autor hinzu zu fügen, muss der admin folgendes tuhen:
```sh
$ curl -X POST http://localhost:8000/create_author   -H "Content-Type: application/x-www-form-urlencoded"   -d "secret_key={key}&author_name={name}"
```

Hierbei müssen `{name}` und `{key}` mit den richtigen values ersetzt werden.