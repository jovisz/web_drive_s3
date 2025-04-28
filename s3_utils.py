import boto3
from botocore.exceptions import ClientError
import config
import mimetypes


def get_content_type(filename):
    """
    Guess the MIME content type of a file based on its filename.

    Args:
        filename (str): The name of the file.

    Returns:
        str: The guessed content type or 'application/octet-stream' if unknown.
    """
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or 'application/octet-stream'


s3 = boto3.client(
    's3',
    aws_access_key_id=config.AWS_ACCESS_KEY,
    aws_secret_access_key=config.AWS_SECRET_KEY,
    region_name=config.AWS_REGION
)


def list_files(prefix='', continuation_token=None, max_keys=20):
    """
    List files and folders in an S3 bucket under a given prefix.

    Args:
        prefix (str): The prefix (folder path) to list.
        continuation_token (str or None): Token for continuing pagination.
        max_keys (int): Maximum number of keys to return.

    Returns:
        tuple: (items (list of dict), next_token (str), is_truncated (bool))
            items: List of dicts with keys 'key', 'size', 'last_modified'.
            next_token: Token for next page or empty string.
            is_truncated: Whether more results are available.
    """
    paginator = s3.get_paginator('list_objects_v2')
    params = {
        'Bucket': config.S3_BUCKET,
        'Prefix': prefix,
        'Delimiter': '/'
    }
    if continuation_token:
        params['ContinuationToken'] = continuation_token
    if max_keys is not None:
        params['MaxKeys'] = max_keys

    page_iterator = paginator.paginate(**params)

    items = []
    next_token = ''
    is_truncated = False

    for page in page_iterator:
        if 'CommonPrefixes' in page:
            for folder in page['CommonPrefixes']:
                items.append({
                    'key': folder['Prefix'],
                    'size': None,
                    'last_modified': None
                })

        if 'Contents' in page:
            for obj in page['Contents']:
                if obj['Key'] != prefix and not obj['Key'].endswith('/'):
                    items.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })

        if page.get('IsTruncated'):
            next_token = page['NextContinuationToken']
            is_truncated = True
        break

    return items, next_token, is_truncated


def upload_files(files, prefix=''):
    """
    Upload multiple files to the S3 bucket under a specified prefix.

    Args:
        files (iterable): Iterable of file-like objects with a 'filename' attribute.
        prefix (str): Prefix path to prepend to each file's key in S3.
    """
    for file in files:
        key = prefix + file.filename
        content_type = get_content_type(file.filename)
        s3.upload_fileobj(
            file,
            config.S3_BUCKET,
            key,
            ExtraArgs={
                'ContentType': content_type
            }
        )


def delete_files(keys):
    """
    Delete multiple objects from the S3 bucket.

    Args:
        keys (list of str): List of object keys to delete.
    """
    objects = [{'Key': key} for key in keys]
    s3.delete_objects(Bucket=config.S3_BUCKET, Delete={'Objects': objects})


def generate_presigned_url(key, expiration=3600, inline=False):
    """
    Generate a presigned URL for accessing an S3 object.

    Args:
        key (str): The S3 object key.
        expiration (int): Time in seconds for the presigned URL to remain valid.
        inline (bool): Whether to set content disposition to inline.

    Returns:
        str or None: The presigned URL or None if generation failed.
    """
    params = {
        'Bucket': config.S3_BUCKET,
        'Key': key
    }
    if inline:
        params['ResponseContentDisposition'] = 'inline'
    try:
        return s3.generate_presigned_url('get_object',
            Params=params,
            ExpiresIn=expiration)
    except ClientError:
        return None


def create_folder_s3(prefix=''):
    """
    Create a folder in S3 by creating a zero-byte object with a trailing slash.

    Args:
        prefix (str): Folder prefix (should end with '/').
    """
    if not prefix.endswith('/'):
        prefix += '/'
    s3.put_object(Bucket=config.S3_BUCKET, Key=prefix)


def delete_keys(keys):
    """
    Delete keys from S3, recursively deleting contents if the key is a folder.

    Args:
        keys (list of str): List of keys or folder prefixes to delete.
    """
    for key in keys:
        if key.endswith('/'):
            objects_to_delete = s3.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=key)
            if 'Contents' in objects_to_delete:
                for obj in objects_to_delete['Contents']:
                    s3.delete_object(Bucket=config.S3_BUCKET, Key=obj['Key'])
        else:
            s3.delete_object(Bucket=config.S3_BUCKET, Key=key)


def estimate_total_count(prefix=''):
    """
    Estimate the total number of objects under a given prefix in the bucket.

    Args:
        prefix (str): Prefix path to count objects under.

    Returns:
        int: Total count of objects excluding the prefix folder itself.
    """
    total = 0
    response = s3.list_objects_v2(
        Bucket=config.S3_BUCKET,
        Prefix=prefix,
        Delimiter='/'
    )
    if 'Contents' in response:
        total = sum(1 for obj in response['Contents'] if obj['Key'] != prefix)
    return total


def get_object_content(key):
    """
    Fetch the binary content and content type of an object from S3.

    Args:
        key (str): The S3 object key

    Returns:
        tuple: (content_bytes, content_type)
    """
    from mimetypes import guess_type

    obj = s3.get_object(Bucket=config.S3_BUCKET, Key=key)
    content = obj['Body'].read()
    content_type, _ = guess_type(key)
    if not content_type:
        content_type = 'application/octet-stream'

    return content, content_type