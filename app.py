from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, Response
from auth import login_required, authenticate, get_user_prefix
from s3_utils import (
    list_files,
    upload_files,
    delete_files,
    generate_presigned_url,
    create_folder_s3,
    delete_keys,
    estimate_total_count,
    get_object_content
)
import config
from flask_login import LoginManager, login_user, logout_user, current_user, UserMixin
import mimetypes
import math
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

@app.template_filter('humansize')
def humansize(size):
    try:
        size = int(size)
    except:
        return '-'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login. On GET, renders login form.
    On POST, authenticates user credentials and starts session.
    """
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        OK, err = authenticate(username, password)
        if OK:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash(err or "Invalid credentials", "danger")
            return render_template('login.html', error=err)

    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Logs the user out and redirects to login page.
    
    Returns:
        - Redirect response to login page.
    """
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """
    Main index route. Lists objects under a given prefix with pagination.
    Shows directories first, then files, ordered by last modified time (descending).
    
    Query Parameters:
        prefix (str): The S3 prefix path to list.
        token (str): Continuation token for pagination (not used).
        limit (int): Number of items per page.
        page (int): Current page number.
        
    Returns:
        - Rendered HTML template 'index.html' with files and pagination info.
        - 403 error if user tries to access unauthorized prefix.
    """
    # Get query parameters
    raw_prefix = request.args.get('prefix', '')
    token = request.args.get('token', '')
    page_size = int(request.args.get('limit', 20))
    page = int(request.args.get('page', 1))

    # Permission check: ensure user can only access their own prefix
    user_prefix = get_user_prefix(session['username'])
    if not raw_prefix:
        raw_prefix = user_prefix
    if not raw_prefix.startswith(user_prefix):
        flash("Unauthorized access", "danger")
        return "Unauthorized access", 403

    # Normalize prefix for listing
    prefix = raw_prefix
    if prefix and not prefix.endswith('/'):
        prefix += '/'

    # List all objects under prefix
    all_items, _, _ = list_files(prefix=prefix, continuation_token='', max_keys=None)

    # Sort items: directories first, then files; order by last_modified descending
    all_items.sort(key=lambda x: (
        not x['key'].endswith('/'),  # False for dirs, True for files — dirs first
        -(x['last_modified'].timestamp() if x['last_modified'] else 0)  # newer first
    ))

    # Filter to only direct children files (exclude subfolders and folders)
    total_count = len([
        f for f in all_items
        if f['key'].startswith(prefix)
        and not f['key'].endswith('/')
        and f['key'].count('/') == prefix.count('/')  # only direct children
    ])

    # Pagination calculation
    total_pages = max(1, math.ceil(total_count / page_size))
    start = (page - 1) * page_size
    end = start + page_size

    # Slice items for current page
    items = all_items[start:end]

    next_token = ''  # not used anymore
    is_truncated = page < total_pages

    return render_template(
        'index.html',
        files=items,
        total_count=total_count,
        username=session['username'],
        prefix=prefix,
        search='',
        token=token,
        next_token=next_token,
        limit=page_size,
        page=page,
        total_pages=total_pages,
        show_prev=page > 1,
        show_next=is_truncated
    )

@app.route('/search')
@login_required
def search():
    """
    Search route. Filters files and folders by name within the current folder only.
    Applies the same sorting and pagination as the index view.
    
    Query Parameters:
        prefix (str): The S3 prefix path to search within.
        query (str): Search string to filter files/folders by name.
        limit (int): Number of items per page.
        page (int): Current page number.
        
    Returns:
        - Rendered HTML template 'index.html' with filtered files and pagination info.
        - 403 error if user tries to access unauthorized prefix.
    """
    # Get query parameters
    raw_prefix = request.args.get('prefix', '')
    search_query = request.args.get('query', '').strip()
    page_size = int(request.args.get('limit', 20))
    page = int(request.args.get('page', 1))

    # Permission check: ensure user can only access their own prefix
    user_prefix = get_user_prefix(session['username'])
    if not raw_prefix:
        raw_prefix = user_prefix
    if not raw_prefix.startswith(user_prefix):
        flash("Unauthorized access", "danger")
        return "Unauthorized", 403

    # Normalize prefix for listing
    prefix = raw_prefix
    if prefix and not prefix.endswith('/'):
        prefix += '/'

    # List all objects under prefix
    all_items, _, _ = list_files(prefix=prefix, continuation_token='', max_keys=None)

    # Filter items by search query within current directory level using last segment name
    filtered = []
    for f in all_items:
        if not f['key'].startswith(prefix):
            continue
        target_name = f['key'].rsplit('/', 2)[-2 if f['key'].endswith('/') else -1]
        if search_query.lower() in target_name.lower():
            # Ensure only direct children or immediate folders are included
            if (not f['key'].endswith('/') and f['key'].count('/') == prefix.count('/')) or \
               (f['key'].endswith('/') and f['key'].count('/') == prefix.count('/') + 1):
                filtered.append(f)

    # Sort filtered items: directories first, then files; order by last_modified descending
    filtered.sort(key=lambda x: (
        not x['key'].endswith('/'),
        -(x['last_modified'].timestamp() if x['last_modified'] else 0)
    ))

    # Pagination calculation
    total_count = len(filtered)
    total_pages = max(1, math.ceil(total_count / page_size))
    start = (page - 1) * page_size
    end = start + page_size

    # Slice items for current page
    items = filtered[start:end]

    return render_template(
        'index.html',
        files=items,
        total_count=total_count,
        username=session['username'],
        prefix=prefix,
        search=search_query,
        token='',
        next_token='',
        limit=page_size,
        page=page,
        total_pages=total_pages,
        show_prev=page > 1,
        show_next=page < total_pages,
        search_mode=True
    )

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    """
    Uploads selected files to the given S3 prefix.
    
    Request Arguments:
        prefix (str): Optional query parameter indicating sub-prefix to upload under.
        files (list): Files uploaded via form-data.
        
    Returns:
        - Redirects back to index page with current prefix.
    """
    prefix = request.args.get('prefix', '').strip('/')
    if prefix and not prefix.endswith('/'):
        prefix += '/'
    files = request.files.getlist('files')
    upload_files(files, prefix)
    return redirect(url_for('index', prefix=prefix))

@app.route('/download')
@login_required
def download():
    """
    Downloads a file from S3 given its key.
    
    Query Parameters:
        key (str): The S3 object key to download.
        
    Returns:
        - Response with file content and appropriate headers for download.
        - 400 error if key is missing.
    """
    key = request.args.get('key')
    if not key:
        return "Missing key", 400

    content, content_type = get_object_content(key)

    filename = key.split('/')[-1]

    response = Response(content, mimetype=content_type)
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response

@app.route('/delete', methods=['POST'])
@login_required
def delete():
    """
    Deletes selected files from S3.
    
    Form Data:
        keys (list): List of S3 keys to delete.
    Query Parameters:
        prefix (str): Current prefix to redirect back to after deletion.
        
    Returns:
        - Redirects back to index page with current prefix.
    """
    keys = request.form.getlist('keys')
    prefix = request.args.get('prefix', '')
    if keys:
        delete_keys(keys)
    return redirect(url_for('index', prefix=prefix))

@app.route('/create-folder', methods=['POST'])
@login_required
def create_folder():
    """
    Creates a new folder (prefix) in S3 under the current user's prefix.
    
    Form Data:
        foldername (str): Name of the folder to create.
    Query Parameters:
        prefix (str): Current prefix to create folder under.
        
    Returns:
        - Redirects back to index page with current prefix.
    """
    foldername = request.form['foldername'].strip('/')
    full_prefix = request.args.get('prefix', '').strip('/')
    if full_prefix and not full_prefix.endswith('/'):
        full_prefix += '/'
    full_path = f"{full_prefix}{foldername}/"
    create_folder_s3(full_path)
    return redirect(url_for('index', prefix=full_prefix))

@app.route('/preview')
@login_required
def preview():
    """
    Provides an inline preview of supported file types (images, pdf, video, svg, txt).
    For unsupported types, redirects to a presigned URL for download.
    
    Query Parameters:
        key (str): The S3 object key to preview.
        
    Returns:
        - HTML snippet to embed the preview.
        - Redirect to presigned URL for unsupported types.
        - 400 error if key is missing.
    """
    key = request.args.get('key')
    if not key:
        return "Missing key", 400

    content_type, _ = mimetypes.guess_type(key)
    if not content_type:
        content_type = 'application/octet-stream'

    url = generate_presigned_url(key, inline=True)

    ext = key.lower().split('.')[-1]
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        return f'<img src="{url}" style="max-width:100%; max-height:90vh;">'
    elif ext == 'pdf':
        return f'<iframe src="{url}" width="100%" height="90%" style="border:none;"></iframe>'
    elif ext == 'mp4':
        return f'<video controls autoplay style="max-width:100%; max-height:90vh;"><source src="{url}" type="video/mp4"></video>'
    elif ext == 'svg':
        return f'<object type="image/svg+xml" data="{url}" width="100%" height="90%"></object>'
    elif ext == 'txt':
        return f'<iframe src="{url}" style="width:100%; height:90vh; border:none;"></iframe>'
    else:
        return redirect(url)

@app.route('/preview-image')
@login_required
def preview_image():
    """
    Returns the raw content of an image file from S3.
    
    Query Parameters:
        key (str): The S3 object key of the image.
        
    Returns:
        - Response with image content and correct MIME type.
        - 400 error if key is missing.
    """
    key = request.args.get('key')
    if not key:
        return "Missing key", 400

    # guess content type
    content_type, _ = mimetypes.guess_type(key)
    if not content_type:
        content_type = 'application/octet-stream'

    content, content_type = get_object_content(key)
    return Response(content, mimetype=content_type)

if __name__ == '__main__':
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", 8080))

    app.run(host=host, port=port, debug=True)