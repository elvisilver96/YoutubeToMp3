from flask import Flask, request, send_file, jsonify
from pytube import YouTube
from pydub import AudioSegment
import os
import re
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Setup rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

# YouTube URL validation regex
YOUTUBE_URL_REGEX = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
)

def sanitize_url(url):
    """Sanitize and validate the URL."""
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ['http', 'https']:
        return None
    query_params = parse_qs(parsed_url.query)
    if 'v' in query_params:
        video_id = query_params['v'][0]
        return f'https://www.youtube.com/watch?v={video_id}'
    if parsed_url.hostname in ['youtu.be']:
        video_id = parsed_url.path.lstrip('/')
        return f'https://www.youtube.com/watch?v={video_id}'
    return url if YOUTUBE_URL_REGEX.match(url) else None

@app.route('/download', methods=['GET'])
@limiter.limit("10 per minute")
def download():
    url = request.args.get('url')
    sanitized_url = sanitize_url(url)
    if not sanitized_url:
        return jsonify({"error": "Invalid URL provided."}), 400

    try:
        video = YouTube(sanitized_url)
        stream = video.streams.filter(only_audio=True).first()

        # Create a temporary file to save the audio
        temp_file_mp4 = 'temp_audio.mp4'
        temp_file_mp3 = 'temp_audio.mp3'

        # Download the stream to a temporary file
        stream.download(filename=temp_file_mp4)

        # Convert the audio stream to MP3
        audio = AudioSegment.from_file(temp_file_mp4, format="mp4")
        audio.export(temp_file_mp3, format="mp3")

        # Send the MP3 file
        return send_file(temp_file_mp3, as_attachment=True, download_name="download.mp3", mimetype="audio/mpeg")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"error": "An internal error occurred. Please try again later."}), 500

    finally:
        # Clean up the temporary files
        if os.path.exists(temp_file_mp4):
            os.remove(temp_file_mp4)
        if os.path.exists(temp_file_mp3):
            os.remove(temp_file_mp3)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "rate limit exceeded"}), 429

if __name__ == '__main__':
    app.run(debug=True)
