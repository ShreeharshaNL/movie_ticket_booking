from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='@Shnl2005',
        database='movie_ticket_booking'
    )

# Decorator to require admin login
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# Home route
@app.route('/')
def home():
    return render_template('home.html')

# ---------------- USER ROUTES ----------------

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['name']
            flash('Login successful!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid credentials, please try again.', 'danger')
            return redirect('/login')

    return render_template('login.html')

# Register route with validations
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        phno = request.form['phno'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not name or not phno or not email or not password:
            return render_template('register.html', error="All fields are required.")

        if not re.fullmatch(r"\d{10}", phno):
            return render_template('register.html', error="Phone number must be 10 digits.")

        if not re.fullmatch(r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&]).{8,}$", password):
            return render_template('register.html', error="Password must be 8+ characters with a letter, number, and special character.")

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match.")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return render_template('register.html', error="Email already registered.")

        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (name, phone, email, password) VALUES (%s, %s, %s, %s)",
                       (name, phno, email, hashed_password))
        conn.commit()
        conn.close()
        return redirect('/login')

    return render_template('register.html')

# User dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies")
    movies = cursor.fetchall()

    for movie in movies:
        # Fetch showtimes for movie (if needed)
        cursor.execute("SELECT * FROM showtimes WHERE movie_id = %s", (movie['id'],))
        showtimes = cursor.fetchall()
        movie['showtimes'] = showtimes

        # Fetch average rating for each movie
        cursor.execute("SELECT AVG(rating) as avg_rating FROM ratings WHERE movie_id = %s", (movie['id'],))
        avg_rating_result = cursor.fetchone()
        movie['avg_rating'] = avg_rating_result['avg_rating'] if avg_rating_result['avg_rating'] is not None else 0

    conn.close()
    return render_template('dashboard.html', movies=movies, username=session['username'])


# Movie details with reviews and average rating
@app.route('/movie/<int:movie_id>')
def view_movie(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    if not movie:
        conn.close()
        return "Movie not found", 404

    cursor.execute("SELECT user_id, rating, review, created_at FROM ratings WHERE movie_id = %s ORDER BY created_at DESC", (movie_id,))
    reviews = cursor.fetchall()

    for r in reviews:
        cursor.execute("SELECT name FROM users WHERE id = %s", (r['user_id'],))
        user = cursor.fetchone()
        r['user_name'] = user['name'] if user else 'Anonymous'

    cursor.execute("SELECT AVG(rating) AS avg_rating, COUNT(*) AS count FROM ratings WHERE movie_id = %s", (movie_id,))
    stats = cursor.fetchone()
    avg_rating = stats['avg_rating'] if stats['avg_rating'] is not None else 0
    review_count = stats['count']

    conn.close()
    return render_template('movie.html', movie=movie, reviews=reviews, avg_rating=avg_rating, review_count=review_count)


# Submit or update rating and review
@app.route('/rate_movie/<int:movie_id>', methods=['POST'])
def rate_movie(movie_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to rate.'}), 401

    user_id = session.get('user_id')
    data = request.get_json()
    rating = data.get('rating')
    review = data.get('review', '').strip()

    if not rating or not (1 <= rating <= 5):
        return jsonify({'success': False, 'message': 'Invalid rating.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM ratings WHERE user_id=%s AND movie_id=%s", (user_id, movie_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE ratings SET rating=%s, review=%s, created_at=NOW() WHERE id=%s",
            (rating, review, existing[0])
        )
    else:
        cursor.execute(
            "INSERT INTO ratings (user_id, movie_id, rating, review) VALUES (%s, %s, %s, %s)",
            (user_id, movie_id, rating, review)
        )

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Rating submitted.'})

@app.route('/select_showtime/<int:movie_id>')
def select_showtime(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    cursor.execute("SELECT * FROM showtimes WHERE movie_id = %s", (movie_id,))
    showtimes = cursor.fetchall()

    conn.close()
    return render_template('select_showtime.html', movie=movie, showtimes=showtimes)


# Seat status route
@app.route('/seats_status/<int:showtime_id>')
def seats_status(showtime_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT seat_number, status FROM seats WHERE showtime_id = %s", (showtime_id,))
    seats = [{'seat_number': row['seat_number'], 'status': row['status']} for row in cursor.fetchall()]
    conn.close()
    return jsonify({'seats': seats})

# Book seats page
@app.route('/book/<int:showtime_id>')
def book_seats(showtime_id):
    return render_template('book_seats.html', showtime_id=showtime_id)

# Handle seat booking
@app.route('/book_seats/<int:showtime_id>', methods=['POST'])
def book_selected_seats(showtime_id):
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Invalid content type. Expected application/json.'}), 400

    data = request.get_json()
    selected_seats = data.get('seats')
    user_id = session.get('user_id')

    if not selected_seats or not user_id:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for seat_number in selected_seats:
            cursor.execute("SELECT id, status FROM seats WHERE showtime_id=%s AND seat_number=%s", (showtime_id, seat_number))
            seat = cursor.fetchone()

            if not seat:
                return jsonify({'success': False, 'error': f'Seat {seat_number} not found'}), 404

            seat_id, seat_status = seat

            if seat_status == 'booked':
                return jsonify({'success': False, 'error': f'Seat {seat_number} already booked'}), 409

            cursor.execute("UPDATE seats SET status='booked' WHERE id=%s", (seat_id,))
            cursor.execute("INSERT INTO bookings (user_id, showtime_id, seat_id) VALUES (%s, %s, %s)", (user_id, showtime_id, seat_id))

        conn.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

# Payment routes
@app.route("/payment", methods=["POST"])
def payment():
    showtime_id = request.form.get("showtime_id")
    seat_ids = request.form.get("seat_ids")
    user_id = request.form.get("user_id")

    return render_template("payment.html", showtime_id=showtime_id, seat_ids=seat_ids, user_id=user_id)

@app.route("/process_payment", methods=["POST"])
def process_payment():
    showtime_id = request.form["showtime_id"]
    seat_ids = request.form["seat_ids"]
    user_id = request.form["user_id"]
    # Add booking logic here...

    return f"Payment successful! Booking confirmed for seats {seat_ids}."

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect('/')


# ---------------- ADMIN ROUTES ----------------

# Admin login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE name = %s AND password = %s", (name, password))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['name']
            flash('Admin login successful!', 'success')
            return redirect('/admin/dashboard')
        else:
            flash('Invalid admin credentials.', 'danger')
            return redirect('/admin/login')

    return render_template('admin_login.html')

# Admin dashboard
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies")
    movies = cursor.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', movies=movies)

# Add movie
@app.route('/admin/add_movie', methods=['GET', 'POST'])
@admin_required
def add_movie():
    if request.method == 'POST':
        title = request.form.get('title')
        genre = request.form.get('genre')
        description = request.form.get('description')

        if not title or not genre or not description:
            flash('All fields are required!', 'danger')
            return render_template('add_movie.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO movies (title, genre, description) VALUES (%s, %s, %s)", (title, genre, description))
        conn.commit()
        conn.close()

        flash('Movie added successfully!', 'success')
        return redirect('/admin/dashboard')

    return render_template('add_movie.html')

# Edit movie
@app.route('/admin/edit_movie/<int:movie_id>', methods=['GET', 'POST'])
@admin_required
def edit_movie(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'GET':
        cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
        movie = cursor.fetchone()
        conn.close()

        if movie:
            return render_template('update_movie.html', movie=movie)
        else:
            flash('Movie not found!', 'danger')
            return redirect('/admin/dashboard')

    # POST
    title = request.form.get('title')
    genre = request.form.get('genre')
    description = request.form.get('description')

    if not title or not genre or not description:
        flash('All fields are required!', 'danger')
        return redirect(request.url)

    try:
        cursor.execute("UPDATE movies SET title=%s, genre=%s, description=%s WHERE id=%s",
                       (title, genre, description, movie_id))
        conn.commit()
        flash('Movie updated successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating movie: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect('/admin/dashboard')

# Delete movie
@app.route('/admin/delete_movie/<int:movie_id>', methods=['POST'])
@admin_required
def delete_movie(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
    conn.commit()
    conn.close()
    flash('Movie deleted successfully!', 'info')
    return redirect('/admin/dashboard')

# Manage showtimes
@app.route('/admin/showtimes/<int:movie_id>', methods=['GET', 'POST'])
@admin_required
def manage_showtimes(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM showtimes WHERE movie_id = %s", (movie_id,))
    showtimes = cursor.fetchall()

    if request.method == 'POST':
        showtime = request.form['showtime']
        venue = request.form['venue']
        cursor.execute("INSERT INTO showtimes (movie_id, show_datetime, venue) VALUES (%s, %s, %s)", (movie_id, showtime, venue))
        conn.commit()
        flash('Showtime added successfully!', 'success')
        return redirect(f'/admin/showtimes/{movie_id}')

    conn.close()
    return render_template('manage_showtimes.html', movie_id=movie_id, showtimes=showtimes)

@app.route('/admin/bookings')
@admin_required
def manage_bookings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            b.id AS booking_id,
            u.name AS user_name,
            m.title AS movie_title,
            s.seat_number,
            t.show_datetime,
            t.venue
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN showtimes t ON b.showtime_id = t.id
        JOIN movies m ON t.movie_id = m.id
        JOIN seats s ON b.seat_id = s.id
        ORDER BY t.show_datetime DESC
    """)
    
    bookings = cursor.fetchall()
    conn.close()

    return render_template('admin_bookings.html', bookings=bookings)

# Admin logout
@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash('Admin logged out.', 'success')
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
