import os, sys

os.chdir(os.path.dirname(__file__))
sys.path.append(os.path.dirname(__file__))
from flask import Flask, jsonify, request, send_file, redirect
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, set_access_cookies
)
import urllib.request
from anki.collection import *
from anki.scheduler.v3 import * 
import auth_db
from lib.media import replacePlayTag, isTTSTag
from lib.dictCard import createDictCardModel
from lib.stats import deck_card_stats
from lib.collection import tryOpenCollection
from lib.logs import getTodayStudiedCards
from pathlib import Path

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
app.config['JWT_TOKEN_LOCATION'] = ['cookies']  # Store JWT in cookies
app.config['JWT_COOKIE_SECURE'] = False         # Set to True in production with HTTPS
app.config['JWT_COOKIE_HTTPONLY'] = True        # Prevent JavaScript from accessing the cookie
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
# disable csrf protection
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
# Set token expiration time 1 day
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 7*86400
app.config['MAX_CONTENT_LENGTH'] = 1024**3
app.config['JWT_COOKIE_SAMESITE'] = 'None'

bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app, supports_credentials=True)

# Path to Anki collection files
COLLECTION_ROOT = "./storage/"

@jwt.unauthorized_loader
def unauthorized_callback(callback):
    return jsonify({
        "message": "Unauthorized, please log in.",
        "redirect": "/auth/login"
    }), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        # if username != "zoey":
        #     return jsonify({"message": "Invalid user name"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        auth_db.add_user(username, hashed_password)
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Login route
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not auth_db.user_exists(username) or not bcrypt.check_password_hash(auth_db.get_password(username), password):
            return jsonify({"message": "Invalid credentials"}), 401

        access_token = create_access_token(identity=username)
        
        response = jsonify({"message": "Login successful"})
        set_access_cookies(response, access_token)  # Set the JWT in a cookie
        return response, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    col = None
    try:
        user= get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        decks = col.decks.all_names_and_ids()
        decks_list = [{"id": deck.id, "name": deck.name} for deck in decks]
        return jsonify(decks_list)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/<string:deck_id>/notes/<string:query>/<string:offset>", methods=["GET"])
@jwt_required()
def get_notes(deck_id, query, offset=0):
    """Get all notes from a deck. Offset is the starting index of the notes."""
    col = None
    try:
        limit = 100
        offset = int(offset)
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        query = query if query else "all"
        note_ids = col.find_notes(f"{query} did:{deck_id}")
        n_notes = len(note_ids)
        if offset >= n_notes:
            return jsonify({"total": n_notes, "notes": []})
        if offset + limit > n_notes:
            limit = n_notes - offset
        note_ids = note_ids[offset:offset+limit]
        def get_title(note_id):
            title = col.get_note(note_id).joined_fields()
            if len (title) > 30:
                title = title[:30] + "..."
            return title
        notes = [{"id":id, "title": get_title(id), "ncards": len(col.get_note(id).cards())} for id in note_ids]
        ret = {
            "total": n_notes,
            "notes": notes
        }
        return jsonify(ret)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/<string:deck_id>/search/<string:query>", methods=["GET"])
@jwt_required()
def search_notes(deck_id, query):
    """Get all notes from a deck. Offset is the starting index of the notes."""
    col = None
    try:
        limit = 100
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        note_ids = col.find_notes(f"{query} did:{deck_id}")
        n_notes = len(note_ids)
        def get_title(note_id):
            title = col.get_note(note_id).joined_fields()
            if len (title) > 30:
                title = title[:30] + "..."
            return title
        notes = [{"id":id, "title": get_title(id), "ncards": len(col.get_note(id).cards())} for id in note_ids]
        ret = {
            "total": n_notes,
            "notes": notes
        }
        return jsonify(ret)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/note/batchremove", methods=["POST"])
@jwt_required()
def batch_remove_note():
    """Remove multiple ntoes."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        data = request.json
        note_ids = data.get("nids")
        if len(note_ids) == 0:
            return jsonify({"error": "No note IDs provided."}), 400
        col.remove_notes(note_ids)
        return jsonify({"message": "Notes removed successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/cards/<string:card_id>/note", methods=["GET"])
@jwt_required()
def get_card_note(card_id):
    """Get a card by ID."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        card = col.get_card(int(card_id)).note()
        fields = card.fields
        keys = card.keys()
        note_data = [[key, field] for key, field in zip(keys, fields)]
        note_id = card.id
        return jsonify({"id": note_id, "note_data": note_data})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/notes/<string:note_id>", methods=["GET"])
@jwt_required()
def get_note(note_id):
    """Get a card by ID."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        note = col.get_note(int(note_id))
        fields = note.fields
        keys = note.keys()
        ret = [[key, field] for key, field in zip(keys, fields)]
        return jsonify(ret)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

#Edit a note
@app.route("/note/update/<string:note_id>", methods=["POST"])
@jwt_required()
def update_note(note_id):
    """Edit a note."""
    col = None
    try: 
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        fields = request.json
        note = col.get_note(int(note_id))
        assert len(fields) == len(note.fields)
        for i, field in enumerate(fields):
            note.fields[i] = field
        col.update_note(note)
        return jsonify({"message": "Note updated successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/<string:deck_id>/add/raw", methods=["POST"])
@jwt_required()
def add_card_raw(deck_id):
    """Add a new card to a deck."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
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
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500
    

@app.route("/deck/<string:deck_id>/add/dict", methods=["POST"])
@jwt_required()
def add_card_dict(deck_id):
    """Add a new card to a deck."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        data = request.json
        word = data.get("word")
        phonetic = data.get("phonetic")
        meanings = data.get("meanings_text")
        origin = data.get("origin")
        audio = data.get("audio")

        # Get dict card model
        if col.models.by_name("KikiDictCard"):
            col.models.remove(col.models.by_name("KikiDictCard")["id"])
        createDictCardModel(col)
        model = col.models.by_name("KikiDictCard")
        note = col.new_note(model)
        print(note.fields)
        note.fields[0] = word
        note.fields[1] = phonetic
        note.fields[2] = audio
        note.fields[3] = meanings
        note.fields[4] = origin

        col.add_note(note, int(deck_id))
        return jsonify({"message": "Card added successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/<string:deck_id>/add/from/<string:card_id>", methods=["GET"])
@jwt_required()
def add_card_from(deck_id, card_id):
    """Add a new card to a deck."""
    col = None
    try:
        # First, duplicate the note
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        note = col.get_card(int(card_id)).note()
        new_note = col.new_note(note.note_type())
        new_note.fields = note.fields
        
        # Add the new note to the deck
        col.add_note(new_note, int(deck_id))
        return jsonify({"message": "Card added successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500
    

@app.route("/card/remove/<string:cid>", methods=["POST"])
@jwt_required()
def remove_card(cid):
    """Add a new card to a deck."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        data = request.json
        cid = int(data.get("cid"))
        card_id = int(cid)
        note_id = col.get_card(card_id).nid
        col.remove_notes([note_id])
        return jsonify({"message": "Card removed successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/card/suspend", methods=["POST"])
@jwt_required()
def suspend_card():
    """Bury a card."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        data = request.json
        card_id = int(data.get("cid"))
        col.sched.suspend_cards([card_id])
        return jsonify({"message": "Card buried successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/study/<string:deck_id>/next", methods=["GET"])
@jwt_required()
def get_next_card(deck_id):
    """
    Get the next card to study from the scheduler.
    """
    col = None
    try:
        # Set the deck for the session
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        deck_id = int(deck_id)
        col.decks.select(deck_id)  # Select the specified deck

        # Get the next card from the scheduler
        new, learning, review = col.sched.counts()
        if (new + learning + review) == 0:
            return jsonify({"message": "No cards to study."}), 404
        queued_card = col.sched.get_queued_cards().cards[0]
        card_id = queued_card.card.id
        card = col.get_card(card_id)

        print(card.timer_started)

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

        intervals = {
            "again": col.sched.nextIvlStr(card, 1),
            "hard": col.sched.nextIvlStr(card, 2),
            "okay": col.sched.nextIvlStr(card, 3),
            "easy": col.sched.nextIvlStr(card, 4)
        }

        card = {
            "cid": card.id,
            "Front": front,  # Front field
            "Back": back,  # Back field
        }

        counts = {
            "new": new,
            "learning": learning,
            "review": review
        }
        # Return the card's details
        return jsonify({
            "card": card,
            "counts": counts,
            "intervals": intervals
        })

    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500


@app.route("/study/answer", methods=["POST"])
@jwt_required()
def answer_card():
    """
    Submit an answer for a card using the scheduler.
    """
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
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
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500
    
@app.route("/deck/add", methods=["POST"])
@jwt_required()
def add_deck():
    """Add a new deck."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        data = request.json
        name = data.get("name")
        col.decks.add_normal_deck_with_name(name)
        return jsonify({"message": "Deck added successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/remove/<string:deck_id>", methods=["GET"])
@jwt_required()
def remove_deck(deck_id):
    """Remove a deck."""
    col=None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        did = int(deck_id)
        col.decks.remove([did])
        return jsonify({"message": "Deck removed successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/config/<string:deck_id>", methods=["GET"])
@jwt_required()
def get_deck_config(deck_id):
    """Get the configuration of a deck."""
    col=None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        did = int(deck_id)
        config = col.decks.config_dict_for_deck_id(did)
        return jsonify(config)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route("/deck/config/<string:deck_id>", methods=["POST"])
@jwt_required()
def set_deck_config(deck_id):
    """Set the configuration of a deck."""
    col=None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        data = request.json

        #=================Update Config=====================
        #Update the deck config
        col.decks.update_config(data)

        #Update the ignore review limit setting, which is only available though the pb2 API. 
        did = int(deck_id)
        config = col.decks.get_deck_configs_for_update(did).all_config[0].config
        conf_req = anki.deck_config_pb2.UpdateDeckConfigsRequest()
        conf_req.configs.append(config)
        conf_req.new_cards_ignore_review_limit = True #This is all these five lines are for, to ignore review limit
        col.decks.update_deck_configs(conf_req)

        # #=================Update Config=====================

        col.sched.resort_conf(data)
        return jsonify({"message": "Deck configuration updated successfully!"})
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({"error": str(e)}), 500

@app.route('/upload/deck', methods=['POST'])
@jwt_required()
def upload_file():
    """Upload an Anki deck file."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        tmp_dir = f"./tmp/{user}"
        Path(tmp_dir).mkdir(parents=True, exist_ok=True)
        filepath = os.path.join(tmp_dir, file.filename)
        file.save(filepath)

        #import the deck
        import_request = ImportAnkiPackageRequest(package_path=filepath)
        col.import_anki_package(import_request)
        # Remove the file
        os.remove(filepath)

        return jsonify({'message': 'File uploaded successfully', 'filename': file.filename}), 200
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({'error': str(e)}), 500

@app.route("/media/<string:filename>", methods=["GET"])
@jwt_required()
def get_media(filename):
    """Get a media file."""
    col = None
    try:
        user = get_jwt_identity()
        base_dir = os.path.join(COLLECTION_ROOT, f"{user}.media")
        file_path = os.path.join(base_dir, filename)
        return send_file(file_path)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({'error': str(e)}), 500

@app.route("/deck/<string:deck_id>/stats", methods=["GET"])
@jwt_required()
def get_deck_stats(deck_id):
    """Get statistics for a deck."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        did = int(deck_id) if int(deck_id) > 0 else col.decks.current()["id"] #use default deck if deck_id is not provided
        stats = deck_card_stats(col, did)
        return jsonify(stats)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({'error': str(e)}), 500

@app.route("/logs/today", methods=["GET"])
@jwt_required()
def get_today_logs():
    """Get statistics for a deck."""
    col = None
    try:
        user = get_jwt_identity()
        collection_path = os.path.join(COLLECTION_ROOT, f"{user}.anki2")
        col = tryOpenCollection(collection_path)
        log = getTodayStudiedCards(col)
        def data_preview(data):
            if len(data) > 30:
                return data[:30] + "..."
            return data
        ret = [{"log_type": l[0],  "nid": l[1], "ord": l[2], "data": data_preview(l[3])} for l in log]
        return jsonify(ret)
    except Exception as e:
        if col:
            col.close()
        app.log_exception(e)
        return jsonify({'error': str(e)}), 500
    
if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host="0.0.0.0", port=5000)

