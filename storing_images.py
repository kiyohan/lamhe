from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import pymysql

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Connect to MySQL
connection = pymysql.connect(host='localhost', user='rohan', password='@0NKmF710')
cursor = connection.cursor()

# Check if the database 'uploads' exists, otherwise create it
cursor.execute('CREATE DATABASE IF NOT EXISTS uploads')
cursor.execute('USE uploads')

# Create the table if it doesn't exist
cursor.execute("""CREATE TABLE IF NOT EXISTS image_details (
    image_id INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    name VARCHAR(500) NOT NULL,
    size INT NOT NULL,
    extension VARCHAR(100),
    img LONGBLOB
);
""")

# Function to check if a file is an image
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# Function to save image details to MySQL table
def save_image_details(filename, size, extension, blob):
    try:
        # Insert image details into the table
        sql = "INSERT INTO image_details (name, size, extension, img) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (filename, size, extension, blob))
        connection.commit()  # Commit the transaction
    except Exception as e:
        print(f"Error: {e}")

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/upload_images', methods=['POST'])
def upload_images():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    
    files = request.files.getlist('file')

    if not files:
        return jsonify({'error': 'No files uploaded'})

    existing_images = set(os.listdir(app.config['UPLOAD_FOLDER']))

    for file in files:
        if file.filename != '' and allowed_file(file.filename):  # Check if file is an image
            if file.filename not in existing_images:
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                existing_images.add(file.filename)
                # Read the file content as bytes
                with open(file_path, 'rb') as f:
                    file_blob = f.read()
                # Save image details to the MySQL table
                save_image_details(
                    filename=file.filename,
                    size=os.path.getsize(file_path),
                    extension=os.path.splitext(file.filename)[1],
                    blob=file_blob
                )

    return jsonify({'message': 'Images uploaded successfully'})

@app.route('/get_uploaded_images')
def get_uploaded_images():
    images = os.listdir(app.config['UPLOAD_FOLDER'])
    return jsonify({'images': images})

@app.route('/uploads/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
