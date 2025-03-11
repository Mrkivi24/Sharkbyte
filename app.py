from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import random
import string

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, user_id INTEGER, likes INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS comments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, user_id INTEGER, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS likes
                 (user_id INTEGER, post_id INTEGER, PRIMARY KEY (user_id, post_id))''')
    conn.commit()
    conn.close()

# Generate a simple CAPTCHA
def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Homepage
@app.route('/')
def index():
    search_query = request.args.get('search', '')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if search_query:
        c.execute('''SELECT posts.id, posts.title, posts.content, posts.likes, users.username 
                     FROM posts JOIN users ON posts.user_id = users.id 
                     WHERE posts.title LIKE ? OR posts.content LIKE ?''', (f'%{search_query}%', f'%{search_query}%'))
    else:
        c.execute('''SELECT posts.id, posts.title, posts.content, posts.likes, users.username 
                     FROM posts JOIN users ON posts.user_id = users.id''')
    posts = c.fetchall()
    conn.close()
    return render_template('index.html', posts=posts, search_query=search_query)

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha = request.form['captcha']
        if captcha != session.get('captcha'):
            flash('Invalid CAPTCHA')
            return redirect(url_for('register'))

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists')
        finally:
            conn.close()
    session['captcha'] = generate_captcha()
    return render_template('register.html', captcha=session['captcha'])

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))

# Create a post
@app.route('/post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = session['user_id']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)", (title, content, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('post.html')

# View a post and its comments
@app.route('/post/<int:post_id>')
def view_post(post_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT posts.id, posts.title, posts.content, posts.likes, users.username 
                 FROM posts JOIN users ON posts.user_id = users.id 
                 WHERE posts.id = ?''', (post_id,))
    post = c.fetchone()
    c.execute('''SELECT comments.content, users.username 
                 FROM comments JOIN users ON comments.user_id = users.id 
                 WHERE comments.post_id = ?''', (post_id,))
    comments = c.fetchall()
    conn.close()
    return render_template('post_detail.html', post=post, comments=comments)

# Add a comment
@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    content = request.form['content']
    user_id = session['user_id']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO comments (post_id, user_id, content) VALUES (?, ?, ?)", (post_id, user_id, content))
    conn.commit()
    conn.close()
    return redirect(url_for('view_post', post_id=post_id))

# Like a post
@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Check if the user has already liked the post
    c.execute("SELECT * FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id))
    if c.fetchone():
        flash('You have already liked this post')
    else:
        c.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (user_id, post_id))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Edit a post
@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, session['user_id']))
    post = c.fetchone()
    if not post:
        flash('You do not have permission to edit this post')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        c.execute("UPDATE posts SET title = ?, content = ? WHERE id = ?", (title, content, post_id))
        conn.commit()
        conn.close()
        return redirect(url_for('view_post', post_id=post_id))
    conn.close()
    return render_template('edit_post.html', post=post)

# Delete a post
@app.route('/delete/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, session['user_id']))
    post = c.fetchone()
    if not post:
        flash('You do not have permission to delete this post')
        return redirect(url_for('index'))

    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    c.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    c.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()
    flash('Post deleted successfully')
    return redirect(url_for('index'))

# User's posts
@app.route('/my_posts')
def my_posts():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT posts.id, posts.title, posts.content, posts.likes, users.username 
                 FROM posts JOIN users ON posts.user_id = users.id 
                 WHERE posts.user_id = ?''', (session['user_id'],))
    posts = c.fetchall()
    conn.close()
    return render_template('my_posts.html', posts=posts)

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=5000)
