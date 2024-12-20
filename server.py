import os, sys
os.chdir(os.path.dirname(__file__))
sys.path.append(os.path.dirname(__file__))
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, set_access_cookies
)
import urllib.request
from anki.collection import *
from anki.scheduler.v3 import * 
import auth_db
from lib.media import *

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
app.config['JWT_TOKEN_LOCATION'] = ['cookies']  # Store JWT in cookies
app.config['JWT_COOKIE_SECURE'] = False         # Set to True in production with HTTPS
app.config['JWT_COOKIE_HTTPONLY'] = True        # Prevent JavaScript from accessing the cookie
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
# disable csrf protection
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
# Set token expiration time 1 day
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400
# app.config['JWT_COOKIE_SAMESITE'] = 'None'

# Redirect to login when not authorized
app.config['JWT_UNAUTHORIZED_VIEW'] = '/auth/login'


bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app, supports_credentials=True)

# Path to your Anki collection file
COLLECTION_PATH = "./storage/foo.anki2"
col = Collection(COLLECTION_PATH)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username != "zoey":
        return jsonify({"message": "Invalid user name"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    auth_db.add_user(username, hashed_password)
    return jsonify({"message": "User registered successfully"}), 201

# Login route
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not auth_db.user_exists(username) or not bcrypt.check_password_hash(auth_db.get_password(username), password):
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(identity=username)
    
    response = jsonify({"message": "Login successful"})
    set_access_cookies(response, access_token)  # Set the JWT in a cookie
    return response, 200

# Logout route (clear cookie)
@app.route('/auth/logout', methods=['GET'])
def logout():
    response = jsonify({"message": "Logout successful"})
    response.set_cookie('access_token_cookie', '', expires=0)  # Clear the cookie
    return response, 200

@app.route("/")
def home():
    return "Welcome to Local Anki Web!"

@app.route("/decks", methods=["GET"])
@jwt_required()
def get_decks():
    """List all decks."""
    decks = col.decks.all_names_and_ids()
    decks_list = [{"id": deck.id, "name": deck.name} for deck in decks]
    return jsonify(decks_list)

@app.route("/deck/<string:deck_id>/cards", methods=["GET"])
@jwt_required()
def get_cards(deck_id):
    """Get all cards from a deck."""
    card_ids = col.find_notes(f"did:{deck_id}")
    cards = [col.get_note(card_id) for card_id in card_ids]
    cards = [{"id":card.id, "Front": card.fields[0], "Back": card.fields[1]} for card in cards]
    return jsonify(cards)

@app.route("/deck/<string:deck_id>/add/raw", methods=["POST"])
@jwt_required()
def add_card_raw(deck_id):
    """Add a new card to a deck."""
    try:
        data = request.json
        front = data.get("front")
        back = data.get("back")

        if not front or not back:
            return jsonify({"error": "Both front and back are required"}), 400
        print(front, back)
        model = col.models.by_name("Basic")
        note = col.new_note(model)
        note.fields[0] = front
        note.fields[1] = back
        col.add_note(note, int(deck_id))
        return jsonify({"message": "Card added successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/deck/<string:deck_id>/add/from/<string:card_id>", methods=["GET"])
@jwt_required()
def add_card_from(deck_id, card_id):
    """Add a new card to a deck."""
    try:
        # First, duplicate the note
        note = col.get_card(int(card_id)).note()
        new_note = col.new_note(note.note_type())
        new_note.fields = note.fields
        
        # Add the new note to the deck
        col.add_note(new_note, int(deck_id))
        return jsonify({"message": "Card added successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/card/remove/<string:cid>", methods=["GET"])
@jwt_required()
def remove_card(cid):
    """Add a new card to a deck."""
    card_id = int(cid)
    note_id = col.get_card(card_id).nid
    col.remove_notes([note_id])
    return jsonify({"message": "Card removed successfully!"})

@app.route("/study/<string:deck_id>/next", methods=["GET"])
@jwt_required()
def get_next_card(deck_id):
    """
    Get the next card to study from the scheduler.
    """
    try:
        # Set the deck for the session
        deck_id = int(deck_id)
        col.decks.select(deck_id)  # Select the specified deck

        # Get the next card from the scheduler
        queued_card = col.sched.get_queued_cards().cards[0]
        card_id = queued_card.card.id
        card = col.get_card(card_id)

        print(card.timer_started)
        if not card:
            return jsonify({"message": "No cards available for study."}), 404

        front = card.question()
        back = card.answer()

        front_tags = col.get_card(card.id).question_av_tags()
        back_tags = col.get_card(card.id).answer_av_tags()
        print(front_tags)
        print(back_tags)

        front_files = []
        for tag in front_tags:
            if isTTSTag(tag):
                front_files.append("tts")
                continue
            front_files.append(tag.filename)
        
        back_files = []
        for tag in back_tags:
            if isTTSTag(tag):
                back_files.append("tts")
                continue
            back_files.append(tag.filename)

        front = replacePlayTag(front, front_files, back_files)
        back = replacePlayTag(back, front_files, back_files)

        card = {
            "cid": card.id,
            "Front": front,  # Front field
            "Back": back,  # Back field
        }

        new, learning, review = col.sched.counts()
        counts = {
            "new": new,
            "learning": learning,
            "review": review
        }

        # Return the card's details
        return jsonify({
            "card": card,
            "counts": counts
        })

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500


@app.route("/study/answer", methods=["POST"])
@jwt_required()
def answer_card():
    """
    Submit an answer for a card using the scheduler.
    """
    try:
        data = request.json
        rating = data.get("rating")  # User's ease rating: 1 = Again, 2 = Hard, 3 = Good, 4 = Easy
        card_id = int(data.get("cid"))  # ID of the card being answered
        time_started = float(data.get("time_started"))  # Time the card was shown to the user

        if rating not in [1, 2, 3, 4]:
            return jsonify({"error": "Invalid ease rating. Must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)."}), 400
        
        rating = CardAnswer.AGAIN if rating == 1 else CardAnswer.HARD if rating == 2 else CardAnswer.GOOD if rating == 3 else CardAnswer.EASY

        # Get the card
        card = col.get_card(card_id)
        card.timer_started = time.time()
        if not card:
            return jsonify({"message": f"Card with ID {card_id} not found."}), 404
        
        states = col._backend.get_scheduling_states(card.id)
        changes = col.sched.answer_card(
            col.sched.build_answer(card=card, states=states, rating=rating)
        )
        return jsonify({"message": "Card answered successfully.", "Card ID": card_id, "Ease": rating})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# @app.route("/download_deck", methods=["POST"])
# @jwt_required()
# def dowload_deck():
#     """Add a new deck."""
#     data = request.json
#     url = data.get("url")
#     urllib.request.urlretrieve(url, "tmp.apkg")
#     import_request = ImportAnkiPackageRequest(package_path="tmp.apkg")
#     col.import_anki_package(import_request)
#     os.remove("tmp.apkg")
#     return jsonify({"message": "Deck added successfully!"})

@app.route("/deck/add", methods=["POST"])
@jwt_required()
def add_deck():
    """Add a new deck."""
    data = request.json
    name = data.get("name")
    col.decks.add_normal_deck_with_name(name)
    return jsonify({"message": "Deck added successfully!"})

@app.route("/deck/remove/<string:deck_id>", methods=["GET"])
@jwt_required()
def remove_deck(deck_id):
    """Remove a deck."""
    did = int(deck_id)
    col.decks.remove([did])
    return jsonify({"message": "Deck removed successfully!"})

@app.route("/deck/config/<string:deck_id>", methods=["GET"])
@jwt_required()
def get_deck_config(deck_id):
    """Get the configuration of a deck."""
    did = int(deck_id)
    config = col.decks.config_dict_for_deck_id(did)
    return jsonify(config)

@app.route("/deck/config/<string:deck_id>", methods=["POST"])
@jwt_required()
def set_deck_config(deck_id):
    """Set the configuration of a deck."""
    data = request.json
    col.decks.update_config(data)
    return jsonify({"message": "Deck configuration updated successfully!"})

@app.route("/card/<string:cid>/<string:side>/audio", methods=["get"])
@jwt_required()
def streamaudio(cid, side):
    if side == "front":
        tags = col.get_card(int(cid)).question_av_tags()
    else:
        tags = col.get_card(int(cid)).answer_av_tags()
    if not tags or isTTSTag(tags[0]):
        return jsonify({"error": "No audio file found for the card."}), 404
    file_path = tags[0].filename
    base_dir = col.media.dir()
    file_path = os.path.join(base_dir, file_path)

    return send_file(
        file_path, 
        mimetype="audio/wav", 
        as_attachment=False)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Save the file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    return jsonify({'message': 'File uploaded successfully', 'filename': file.filename}), 200

@app.route("/media/<string:filename>", methods=["GET"])
def get_media(filename):
    base_dir = col.media.dir()
    file_path = os.path.join(base_dir, filename)
    return send_file(file_path)

if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host="0.0.0.0", port=5000)
