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
from moviepy.editor import concatenate_audioclips
from moviepy.audio.io.AudioFileClip import AudioFileClip ,AudioClip
from moviepy.editor import ImageSequenceClip, concatenate_videoclips
import shutil
import cv2
import numpy as np
import base64
import urllib.parse
import time
import psycopg2
import subprocess
import glob
from datetime import datetime
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



# # Establish database connection
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




@app.route('/video')
def video(folder_path='selected-images', output_path='output_video.mp4', fps=24, duration_per_image=3):
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    static_video_folder = os.path.join(static_folder, 'video')
    selected_audio_folder = os.path.join(os.path.dirname(__file__), 'selected-audio')
    os.makedirs(static_video_folder, exist_ok=True)
    
    for filename in os.listdir(static_video_folder):
        file_path = os.path.join(static_video_folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Generate a new filename with timestamp
    timestamp = int(time.time())
    output_video_path = f'output_video_{timestamp}.mp4'
    # Adjust the output path to save the video inside the static/video folder
    output_path = os.path.join(static_video_folder, output_video_path)

    image_files = [f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
    image_files.sort()

    if not image_files:
        return jsonify({'message': "No images found in the folder."})

    clips = []

    # Add default audio as the first clip
    audio_files = [f for f in os.listdir(selected_audio_folder) if f.endswith('.mp3')]
    if audio_files:
        audio_path = os.path.join(selected_audio_folder, audio_files[0])
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration

        # Trim audio if longer than video duration
        total_video_duration = len(image_files) * duration_per_image
        if audio_duration > total_video_duration:
            audio_clip = audio_clip.subclip(0, total_video_duration)

        # Repeat audio if shorter than video duration
        while audio_clip.duration < total_video_duration:
            audio_clip = concatenate_audioclips([audio_clip, audio_clip])

        clips.append(audio_clip.set_duration(total_video_duration))

    for img_file in image_files:
        img_path = os.path.join(folder_path, img_file)
        img_clip = ImageSequenceClip([img_path], fps=fps)
        clips.append(img_clip.set_duration(duration_per_image))

    # Filter out audio clips
    video_clips = [clip for clip in clips if not isinstance(clip, AudioClip)]

    final_clip = concatenate_videoclips(video_clips, method="compose") # method compose for video and audio
    
    # Set audio for the final clip
    for clip in clips:
        if isinstance(clip, AudioClip):
            final_clip = final_clip.set_audio(clip)

    # Write video in chunks instead of processing the entire clip at once
    chunk_duration = 10  # Duration of each chunk in seconds
    num_chunks = int(np.ceil(final_clip.duration / chunk_duration))

    for i in range(num_chunks):
        start_time = i * chunk_duration
        end_time = min((i + 1) * chunk_duration, final_clip.duration)
        chunk = final_clip.subclip(start_time, end_time)
        chunk_output_path = output_path.replace('.mp4', f'_chunk_{i}.mp4')
        chunk.write_videofile(chunk_output_path, codec='libx264', fps=fps)

    # Delete the original images after video creation
    for file in image_files:
        file_path = os.path.join(folder_path, file)
        os.remove(file_path)

    video_urls = [url_for('static', filename=f'video/{output_video_path}'.replace('.mp4', f'_chunk_{i}.mp4')) for i in range(num_chunks)]
    message = "Video created successfully!"
    return jsonify({'video_url': video_urls, 'message': message})












@app.route('/get_audio_files')
def get_audio_files():
    audio_files = os.listdir('static/audio')
    audio_data = {}
    for filename in audio_files:
        filepath = os.path.join('static/audio', filename)
        with open(filepath, 'rb') as file:
            audio_data[filename] = base64.b64encode(file.read()).decode('utf-8')
    return jsonify(audio_data)


@app.route('/select_audio', methods=['POST'])
def select_audio():
    data = request.json
    filename = data.get('filename')
    if not filename:
        return 'No filename provided.', 400

    selected_audio_folder = 'selected-audio'

    # Check if the selected-audio folder exists, and if not, create it
    if not os.path.exists(selected_audio_folder):
        os.makedirs(selected_audio_folder)
    else:
        # If the folder exists, empty it by deleting all files
        files_in_folder = os.listdir(selected_audio_folder)
        for file_in_folder in files_in_folder:
            file_path = os.path.join(selected_audio_folder, file_in_folder)
            os.remove(file_path)

    # Ensure that the selected audio file has a .mp3 extension
    filename = filename.split('.')[0] + '.mp3'

    # Convert base64 encoded audio data to bytes
    audio_data_base64 = data.get('audioData')
    audio_data = base64.b64decode(audio_data_base64)

    # Write the audio data to the selected-audio folder as an MP3 file
    selected_audio_path = os.path.join(selected_audio_folder, filename)
    with open(selected_audio_path, 'wb') as file:
        file.write(audio_data)

    return 'Audio file selected and stored successfully.', 200


if __name__ == '__main__':
    app.run(debug=True)
