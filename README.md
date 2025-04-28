# Web Drive S3

A lightweight Flask-based file browser for AWS S3.  
Supports user login, S3 prefix isolation, file preview, upload, batch deletion, folder creation, and scoped search.

---

## 🚀 Features

- 🔐 User login with S3 prefix-based access control
- 📂 Directory-style S3 object listing
- 📥 File upload (multi-select)
- 🗑️ Batch delete selected files
- 📎 Inline preview for images
- 📁 Folder creation
- 🔍 Search within the current directory by file or folder name
- 📊 Show number of selected files in real-time
- 🔢 Auto-sorting: folders first, then files sorted by last modified time (newest first)

---

## 📁 Project Structure

```
web_drive_s3/
├── app.py             # Main Flask application (routes + business logic)
├── auth.py            # Login and S3 prefix authorization
├── s3_utils.py        # AWS S3 interaction helper functions
├── config.py          # Configuration file for AWS credentials and users
├── templates/
│   ├── login.html     # Login page template
│   └── index.html     # Main file browser UI
├── requirements.txt   # Python dependencies
└── Dockerfile         # Docker build configuration
```

---

## ⚙️ Configuration

Edit `config.py`:

```python
USERS = {
    'admin': {'password': 'admin', 'prefix': ''},
    'user1': {'password': '123456', 'prefix': 'user1/'}
}

AWS_ACCESS_KEY = "your-access-key"
AWS_SECRET_KEY = "your-secret-key"
S3_BUCKET = "your-s3-bucket"
AWS_REGION = "your-region"
```

- Admin (`prefix=''`) can access the entire bucket
- Regular users are restricted to their own subdirectories

---

## 🐳 Docker Deployment

### Build the Docker Image

```bash
docker build -t web-drive-s3 .
```

### Run the Container

```bash
docker run -d -p 8080:8080 --name s3drive web-drive-s3
```

Override host and port if needed:

```bash
docker run -d -p 8080:8080 -e APP_HOST=0.0.0.0 -e APP_PORT=8080 web-drive-s3
```

---

## 🌐 Usage

1. Open your browser and navigate to `http://localhost:8080`
2. Login using credentials from `config.py`
3. Use the UI to:
   - Browse directories
   - Upload files
   - Preview images
   - Delete multiple files
   - Create new folders
   - Search by filename in the current directory
   - Directories are always listed before files
   - Files within a folder are sorted by their last modified time, most recent first
---

## 🔐 Access Control

- Each logged-in user is restricted to operate within their assigned S3 prefix.
- Unauthorized attempts to access other prefixes return HTTP 403.

---

## 📝 Notes

- Built with Python 3, Flask, and Boto3
- Lightweight, no database dependency
- Easy to deploy and extend for internal file management needs

---