from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Function to connect to MySQL database
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

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phno']
        address = request.form['address']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, phone, address, email, password) VALUES (%s, %s, %s, %s, %s)",
                (name, phone, address, email, hashed_password)
            )
            conn.commit()
            conn.close()
            flash('Registration successful! You can now log in.', 'success')
            return redirect('/login')
        except mysql.connector.Error as err:
            flash(f"Error: {err}", 'danger')
            return redirect('/register')

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
        cursor.execute("SELECT * FROM showtimes WHERE movie_id = %s", (movie['id'],))
        showtimes = cursor.fetchall()
        movie['showtimes'] = showtimes

    conn.close()
    return render_template('dashboard.html', movies=movies, username=session['username'])

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

@app.route("/payment", methods=["POST"])
def payment():
    # These values should be passed from the seat selection page
    showtime_id = request.form.get("showtime_id")
    seat_ids = request.form.get("seat_ids")  # e.g., "12,13,14"
    user_id = request.form.get("user_id")

    return render_template("payment.html", showtime_id=showtime_id, seat_ids=seat_ids, user_id=user_id)

@app.route("/process_payment", methods=["POST"])
def process_payment():
    # Process payment here
    # You can also insert the booking into the database

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

# Public movie listing
@app.route('/visitor/movies')
def visitor_movies():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies")
    movies = cursor.fetchall()
    conn.close()
    return render_template('movies.html', movies=movies)

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
            flash('Invalid credentials. Please try again.', 'danger')
            return redirect('/admin/login')

    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movies")  # Ensure you're fetching movies here
    movies = cursor.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', movies=movies)



# Add movie
@app.route('/admin/add_movie', methods=['GET', 'POST'])
@admin_required
def add_movie():
    if request.method == 'POST':
        print(request.form)  # Print form data for debugging
        title = request.form.get('title')
        genre = request.form.get('genre')
        description = request.form.get('description')

        if not title or not genre or not description:
            flash('All fields are required!', 'error')
            return render_template('add_movie.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO movies (title, genre, description) VALUES (%s, %s, %s)", (title, genre, description))
        conn.commit()
        conn.close()

        flash('Movie added successfully!', 'success')
        return redirect('/admin/dashboard')

    return render_template('add_movie.html')

# Admin edit movie route
@app.route('/admin/edit_movie/<int:movie_id>', methods=['GET', 'POST'])
@admin_required
def edit_movie(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check for the GET request to fetch the movie details
    if request.method == 'GET':
        cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
        movie = cursor.fetchone()  # Fetch the movie data

        # Check if movie is found
        if movie is None:
            flash('Movie not found!', 'danger')
            return redirect('/admin/dashboard')

        # Close connection after data fetch
        conn.close()

        # Pass movie data to the template
        return render_template('update_movie.html', movie=movie)

    # POST request for updating movie
    if request.method == 'POST':
        title = request.form.get('title')
        genre = request.form.get('genre')
        description = request.form.get('description')

        if not title or not genre or not description:
            flash('All fields are required!', 'danger')
            return redirect(request.url)

        # Update the movie details in the database
        try:
            cursor.execute("UPDATE movies SET title=%s, genre=%s, description=%s WHERE id=%s",
                           (title, genre, description, movie_id))
            conn.commit()
            flash('Movie updated successfully!', 'success')
        except Exception as e:
            conn.rollback()  # Rollback in case of error
            flash(f'Error updating movie: {str(e)}', 'danger')
        finally:
            conn.close()

        return redirect('/admin/dashboard')




@app.route('/admin/delete_movie/<int:movie_id>', methods=['POST'])
@admin_required
def delete_movie(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete movie from the database
    cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
    
    # Commit changes and close the connection
    conn.commit()
    conn.close()
    
    flash('Movie deleted successfully!', 'info')  # Flash a success message
    return redirect('/admin/dashboard')  # Redirect back to the dashboard



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
        cursor.execute("INSERT INTO showtimes (movie_id, showtime) VALUES (%s, %s)", (movie_id, showtime))
        conn.commit()
        flash('Showtime added successfully!', 'success')
        return redirect(f'/admin/showtimes/{movie_id}')

    conn.close()
    return render_template('manage_showtimes.html', movie_id=movie_id, showtimes=showtimes)

# View bookings
@app.route('/admin/bookings')
@admin_required
def manage_bookings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.id, u.name AS user_name, m.name AS movie_name, s.seat_number, s.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN showtimes t ON b.showtime_id = t.id
        JOIN seats s ON b.seat_id = s.id
        JOIN movies m ON t.movie_id = m.id
    """)
    bookings = cursor.fetchall()
    conn.close()
    return render_template('manage_bookings.html', bookings=bookings)

# Admin logout
@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.clear()
    flash('Admin logged out.', 'success')
    return redirect('/')

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
