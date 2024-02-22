# Import necessary modules
import os
from flask import Flask, request, render_template, redirect, send_from_directory,session,jsonify
import pymysql
import pickle
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='static', template_folder='static')

app.secret_key = 'hello,world!'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database configuration
db_config = {
    "host": "localhost",    
    "user": "akmal",
    "password": "Akmal18@",
    "db": "lamhe",
}



# Establish database connection
def get_db_connection():
    return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **db_config)

# Initialize database
def init_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Create User_Details table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                name VARCHAR(255),
                email VARCHAR(255),
                password VARCHAR(255)
            )
        """)

        # Create Images table
        cursor.execute("""CREATE TABLE IF NOT EXISTS image_details (
            image_id INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
            username VARCHAR(255) ,
            name VARCHAR(500) NOT NULL,
            size INT NOT NULL,
            extension VARCHAR(100),
            img LONGBLOB
        );
        """)

        connection.commit()

        cursor.close()
        connection.close()
        
        print("Database and tables initialization successful.")

    except Exception as e:
        print(f"An error occurred during database initialization: {e}")

# Initialize database when the app starts
init_db()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')



# Your login route
from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form['Uname']
        name = request.form['name']
        email = request.form['email']
        password = request.form['Pass']
        confirmPassword = request.form['confrm_Pass']

        if password != confirmPassword:
            return "Passwords do not match.", 400
        
        try:
            # Hash the password
            hashed_password = generate_password_hash(password)

            # Open a connection to the database
            connection = get_db_connection()
            cursor = connection.cursor()

            # Insert user data into the database
            cursor.execute("INSERT INTO users (username, name, email, password) VALUES (%s, %s, %s, %s)",
                           (username, name, email, hashed_password))

            # Commit the transaction
            connection.commit()

            # Close cursor and connection
            cursor.close()
            connection.close()

            return redirect('/success')

        except Exception as e:
            return f"An error occurred: {e}", 500

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        username = request.form['Uname']
        password = request.form['Pass']

        if username == 'admin' and password == 'admin':  # Check if it's the admin login
            try:
                connection = get_db_connection()
                cursor = connection.cursor()

                cursor.execute("SELECT id, username, name, email FROM users")
                users = cursor.fetchall()

                cursor.close()
                connection.close()

                return render_template('admin.html', users=users)

            except Exception as e:
                return f"An error occurred: {e}", 500

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            cursor.close()
            connection.close()

            if user and check_password_hash(user['password'], password):
                # Store the username in the session
                session['username'] = username
                return redirect('/home')  # Redirect to the home page after successful login

            return redirect('/fail')  # Redirect to the login failure page

        except Exception as e:
            return f"An error occurred: {e}", 500
        
@app.route('/home')
def home():
    username = session.get('username')
    if not username:
        return redirect('/')
    # print(session('username'))
    
    return render_template('home.html', username=username)

    

# Route for handling failed login attempts
@app.route('/fail')
def fail():
    return send_from_directory('static', 'invalid_credentials.html')

        

@app.route('/success')
def success():
    return send_from_directory('static', 'succes.html')

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the user session
    session.clear()
    return redirect('/')  # Redirect to the home page after logout




# Route to upload images
@app.route('/upload_images', methods=['POST'])
def upload_images():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')

    if not files:
        return jsonify({'error': 'No files uploaded'}), 400

    try:
        # Retrieve the username from the session
        username = session.get('username')
        if not username:
            return jsonify({'error': 'User not logged in'}), 401

        connection = get_db_connection()
        cursor = connection.cursor()

        for file in files:
            if file.filename != '' and allowed_file(file.filename):  # Check if file is an image
                # Check if the file with the same name exists for the user
                cursor.execute("SELECT * FROM image_details WHERE username = %s AND name = %s", (username, file.filename))
                existing_image = cursor.fetchone()
                if existing_image:
                    return jsonify({'error': f"File '{file.filename}' already exists"}), 400
                
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                # Read the file content as bytes
                with open(file_path, 'rb') as f:
                    file_blob = f.read()
                # Save image details to the MySQL table along with the current user's username
                save_image_details(
                    connection=connection,
                    cursor=cursor,
                    username=username,
                    filename=file.filename,
                    size=os.path.getsize(file_path),
                    extension=os.path.splitext(file.filename)[1],
                    blob=file_blob
                )

        connection.commit()  # Commit all changes to the database

        return jsonify({'message': 'Images uploaded successfully'}), 200

    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500

    finally:
        cursor.close()
        connection.close()


@app.route('/get_uploaded_images')
def get_uploaded_images():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    username = session['username']
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT name FROM image_details WHERE username = %s", (username,))
        images = [row['name'] for row in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        return jsonify({'images': images})
    
    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500



@app.route('/uploads/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Function to check if a file is an image
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# Function to save image details to MySQL table
def save_image_details(connection, cursor, username, filename, size, extension, blob):
    try:
        # Insert image details into the table
        sql = "INSERT INTO image_details (username, name, size, extension, img) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (username, filename, size, extension, blob))
        connection.commit()  # Commit the transaction
    except Exception as e:
        print(f"Error: {e}")



# Main entry point of the application
if __name__ == '__main__':
    app.run(debug=True)
