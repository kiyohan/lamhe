# Import necessary modules
import os
from flask import Flask, request, render_template, redirect, send_from_directory,session,jsonify,send_file,url_for
import pymysql
import pickle
import io
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from PIL import Image
from moviepy.editor import ImageSequenceClip, concatenate_videoclips
import cv2
import numpy as np
import base64

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='static', template_folder='static')
app.secret_key = 'Helloworld'
UPLOAD_FOLDER = 'uploads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['JWT_SECRET_KEY'] = '140-073-212'  # Change this to a random secret key

jwt = JWTManager(app)



# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database configuration
db_config = {
    "host": "localhost",    
    "user": "rohan",
    "password": "@0NKmF710",
    "db": "lamhe",
}



# Establish database connection
# def get_db_connection():
#     return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **db_config)
def get_db_connection():
    conn = psycopg2.connect("postgresql://akmalali59855_gmail_:J-3IiGnvZtnFfRZ1CVKh_g@stream-strider-4060.7s5.aws-ap-south-1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full")
    # print("DATABASE_URL: ", os.environ["DATABASE_URL"])
    return conn

# Initialize database
def init_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Create User_Details table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT  PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                name VARCHAR(255),
                email VARCHAR(255),
                password VARCHAR(255)
            )
        """)

        # Create Images table
        cursor.execute("""CREATE TABLE IF NOT EXISTS image_details (
            image_id INT PRIMARY KEY NOT NULL ,
            username VARCHAR(255) ,
            name VARCHAR(500) NOT NULL,
            size INT NOT NULL,
            extension VARCHAR(100),
            img BYTEA
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
            # print(user)
            user = {
                'id': user[0],
                'username': user[1],
                'name': user[2],
                'email': user[3],
                'password': user[4]
            }

            cursor.close()
            connection.close()

            if user and check_password_hash(user['password'], password):
                # Create access token containing user identity
                access_token = create_access_token(identity=username)
                print(access_token)
                session['username'] = username
                return redirect('/home')
                

            return redirect('/fail')

        except Exception as e:
            return jsonify({'error': f"An error occurred: {e}"}), 500

@app.route('/protected')
@jwt_required()  # Require a valid JWT token for accessing this route
def protected():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200
        

        
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

@app.route('/logout')
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
        
        images = [row[0] for row in cursor.fetchall()]
        print(images)

        
        cursor.close()
        connection.close()
        
        return jsonify({'images': images})
    
    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500



@app.route('/uploads/<path:filename>')
def serve_image(filename):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Retrieve image blob based on the filename
        cursor.execute("SELECT img FROM image_details WHERE name = %s", (filename,))
        image_data = cursor.fetchone()

        cursor.close()
        connection.close()


        if image_data:
            return send_file(BytesIO(image_data[0]), mimetype='image/jpeg')  # Adjust mimetype if needed
        else:
            return jsonify({'error': 'Image not found'}), 404

    except Exception as e:
        return jsonify({'error': f"An error occurred: {e}"}), 500


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



@app.route('/upload_selected_images', methods=['POST'])
def upload_selected_images():
    uploaded_files = []
    for blob in request.files.getlist('file'):
        # Convert blob to image file
        image_data = blob.read()
        image_name = blob.filename
        image_path = os.path.join('selected-images', image_name)
        with open(image_path, 'wb') as f:
            f.write(image_data)
        uploaded_files.append(image_name)

    return jsonify({'message': 'Images uploaded successfully', 'files': uploaded_files}), 200

def resize_image(image, target_size):
    return image.resize(target_size)

folder_name = 'selected-images'
output_video_path = 'output_video.mp4'

@app.route('/video')
def video(folder_path=folder_name, output_path=output_video_path, fps=24, duration_per_image=3):
    # Define the path for the video folder within the static directory
    static_video_folder = os.path.join('static', 'video')
    os.makedirs(static_video_folder, exist_ok=True)  # Create the video folder if it doesn't exist

    # Adjust the output path to save the video inside the static/video folder
    output_path = os.path.join(static_video_folder, output_video_path)

    image_files = [f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
    image_files.sort()  # Ensure images are sorted properly
    
    if not image_files:
        print("No images found in the folder.")
        return
    files = os.listdir(folder_path)
    max_width=1024
    max_height=1024

    print(f"Max dimensions: {max_width}x{max_height}")

    # Resize images to match the maximum dimensions
    images_resized = []
    for img_file in image_files:
        img_path = os.path.join(folder_path, img_file)
        with Image.open(img_path) as img:
            resized_img = resize_image(img, (max_width, max_height))
            # Convert image to numpy array and ensure it has only 3 channels (RGB)
            resized_img = np.array(resized_img)[:,:,:3]
            images_resized.append(resized_img)

    # Calculate the number of frames for each image based on the duration
    num_frames_per_image = int(duration_per_image * fps)

    # Construct the ImageSequenceClip for each image with specified duration
    clips = []
    for img in images_resized:
        clips.append(ImageSequenceClip([img], fps=fps).set_duration(duration_per_image))

    # Concatenate all clips to form the final video
    final_clip = concatenate_videoclips(clips)
    # Write the final video to the output path inside the static/video folder
    final_clip.write_videofile(output_path, codec='libx264')
    # Retrieve audio files from the database
    for file in files:
        file_path = os.path.join(folder_path, file)
        os.remove(file_path)
    # return render_template('audio.html')
    video_url = url_for('static', filename='video/output_video.mp4')
    message = "Video created successfully!"
    # return send_file(output_path, mimetype=mimetype, as_attachment=True)
    return jsonify({'video_url': video_url, 'message': message})

if __name__ == '__main__':
    app.run(debug=True)
