from flask import Flask
from jinja2 import StrictUndefined
import os

app = Flask(__name__)
app.jinja_env.undefined = StrictUndefined
app.config['SECRET_KEY'] = b'WR#&f&+%78er0we=%799eww+#7^90-;s'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['DATA_FOLDER'] = os.path.join(basedir, 'data')
app.config['UPLOAD_FOLDER'] = os.path.join(app.config['DATA_FOLDER'], 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
# app.config['MAX_CONTENT_LENGTH'] = 8

from app import views
