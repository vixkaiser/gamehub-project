from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = "eceburceselin123"

# MongoDB bağlantısı
client = MongoClient("mongodb+srv://ecebayyar:ece12345@cluster0.psvtf1r.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["game_distribution_service"] 
games_collection = db["games"]             
users_collection = db["users"]             

# Ana Sayfa
@app.route('/')
def home():
    current_user = session.get("username")
    games = list(games_collection.find({}, {"_id": 0}))[:6]
    return render_template("home.html", current_user=current_user, games=games)

# Kullanıcı Giriş (Form Gösterimi + Post)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        if not username:
            return "Username is required.", 400

        user = users_collection.find_one({"name": username})
        if user:
            session["username"] = username
            return redirect(url_for('user_page', name=username))
        else:
            return render_template("login.html", users=[], error="User not found.")

    users = list(users_collection.find({}, {"_id": 0, "name": 1}))
    return render_template("login.html", users=users)


@app.route('/logout')
def logout():
    session.pop("username", None)  # oturumu siler
    return redirect(url_for("home"))  # ana sayfaya yönlendirir

# Kullanıcı Sayfası (HTML)
@app.route('/user_page')
def user_page():
    username = request.args.get('name')
    if not username:
        return "Username is required.", 400

    user = users_collection.find_one({"name": username}, {"_id": 0})
    if not user:
        return f"Could not find {username}.", 404

    all_games = list(games_collection.find({}, {"_id": 0, "name": 1}))
    return render_template("user_page.html", user=user, games=all_games)

# Kullanıcı Ekle (API)
@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.json
    if "name" not in data:
        return jsonify({"error": "Name field is required"}), 400

    user = {
        "name": data["name"],
        "total_play_time": 0,
        "average_rating": 0,
        "most_played_game": None,
        "comments": [],
        "play_log": {}
    }

    users_collection.insert_one(user)
    return jsonify({"message": "User added successfully!"}), 201

# Kullanıcı Ekle (Form)
@app.route('/add_user_form', methods=['GET', 'POST'])
def add_user_form():
    if request.method == 'POST':
        username = request.form.get('name')
        if not username:
            return "Username is required.", 400

        existing_user = users_collection.find_one({"name": username})
        if existing_user:
            return f"{username} already exists!", 400

        user = {
            "name": username,
            "total_play_time": 0,
            "average_rating": 0,
            "most_played_game": None,
            "comments": [],
            "play_log": {}
        }

        users_collection.insert_one(user)
        return f"{username} added successfully! <br><a href='/'>← Home Page</a>"

    return render_template("add_user.html")

# Oyunları Listele (HTML)
@app.route('/games_page')
def games_page():
    games = list(games_collection.find({}, {"_id": 0}))
    return render_template("games.html", games=games)

# Oyun Ekle (API)
@app.route('/add_game', methods=['POST'])
def add_game():
    data = request.json
    required_fields = ['name', 'genres', 'photo']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    game = {
        "name": data["name"],
        "genres": data["genres"],
        "photo": data["photo"],
        "play_time": 0,
        "rating": 0,
        "all_comments": [],
        "enable_comments": True
    }

    if "optional1" in data:
        game["optional1"] = data["optional1"]
    if "optional2" in data:
        game["optional2"] = data["optional2"]

    games_collection.insert_one(game)
    return jsonify({"message": "Game added successfully!"}), 201

@app.route('/manage')
def manage_page():
    return render_template("manage.html")


@app.route('/remove_game', methods=['POST'])
def remove_game():
    name = request.form.get('name')
    if not name:
        return "Game name is required.", 400

    # Oyun bulunamazsa hata ver
    game = games_collection.find_one({"name": name})
    if not game:
        return f"Game '{name}' not found.", 404

    # Tüm kullanıcıları al
    users = users_collection.find({})
    for user in users:
        username = user["name"]
        updated_fields = {}

        # Yorumu varsa sil
        old_comments = user.get("comments", [])
        new_comments = [c for c in old_comments if c["game"] != name]
        if len(new_comments) != len(old_comments):
            updated_fields["comments"] = new_comments

        # Rating varsa sil ve average'ı yeniden hesapla
        ratings = user.get("ratings", {})
        if name in ratings:
            del ratings[name]
            updated_fields["ratings"] = ratings
            if ratings:
                average = sum(ratings.values()) / len(ratings)
            else:
                average = 0
            updated_fields["average_rating"] = average

        # Play_log'tan oyunu sil (ama total_play_time değişmeyecek)
        play_log = user.get("play_log", {})
        if name in play_log:
            del play_log[name]
            updated_fields["play_log"] = play_log

            # most_played_game güncelle
            if play_log:
                most_played = max(play_log, key=play_log.get)
                updated_fields["most_played_game"] = most_played
            else:
                updated_fields["most_played_game"] = None

        # Güncellemeyi uygula
        if updated_fields:
            users_collection.update_one(
                {"name": username},
                {"$set": updated_fields}
            )

    # Oyunu tamamen sil
    games_collection.delete_one({"name": name})
    return f"Game '{name}' and all related data removed. <br><a href='/'>← Home Page</a>"


@app.route('/remove_user', methods=['POST'])
def remove_user():
    data = request.json
    username = data.get("name")

    if not username:
        return jsonify({"error": "User name is required"}), 400

    user = users_collection.find_one({"name": username})
    if not user:
        return jsonify({"error": f"User '{username}' not found."}), 404

    # Bu alanlar eksikse bile boş değerlerle devam edilsin
    play_log = user.get("play_log") or {}
    ratings = user.get("ratings") or {}
    comments = user.get("comments") or []

    # Her oyun için kullanıcı etkilerini sil
    for game_name in play_log:
        game = games_collection.find_one({"name": game_name})
        if not game:
            continue

        # Play time'dan düş
        user_hours = play_log[game_name]
        games_collection.update_one(
            {"name": game_name},
            {"$inc": {"play_time": -user_hours}}
        )

        # Yorumları sil
        updated_comments = [c for c in game.get("all_comments", []) if c.get("user") != username]
        games_collection.update_one(
            {"name": game_name},
            {"$set": {"all_comments": updated_comments}}
        )

        # Rating tekrar hesapla
        other_users = users_collection.find({f"ratings.{game_name}": {"$exists": True}})
        total_weighted = 0
        total_play = 0
        for u in other_users:
            if u["name"] == username:
                continue
            time = u.get("play_log", {}).get(game_name, 0)
            rate = u.get("ratings", {}).get(game_name, 0)
            total_weighted += time * rate
            total_play += time

        new_rating = total_weighted / total_play if total_play > 0 else 0
        games_collection.update_one(
            {"name": game_name},
            {"$set": {"rating": new_rating}}
        )

    # Kullanıcıyı sil
    users_collection.delete_one({"name": username})

    return jsonify({"message": f"User '{username}' and all their effects have been removed."}), 200


@app.route('/disable_rating_comment', methods=['POST'])
def disable_rating_comment():
    data = request.json
    if "name" not in data:
        return jsonify({"error": "Game name is required"}), 400

    games_collection.update_one({"name": data["name"]}, {"$set": {"enable_comments": False}})
    return jsonify({"message": "Comments and rating disabled for the game!"}), 200


@app.route('/enable_rating_comment', methods=['POST'])
def enable_rating_comment():
    data = request.json
    if "name" not in data:
        return jsonify({"error": "Game name is required"}), 400

    games_collection.update_one({"name": data["name"]}, {"$set": {"enable_comments": True}})
    return jsonify({"message": "Comments and rating enabled for the game!"}), 200


@app.route('/play_game', methods=['POST'])
def play_game():
    username = request.form.get('username')
    game_name = request.form.get('game_name')
    hours = request.form.get('hours')

    if not username or not game_name or not hours:
        return "All fields are required", 400

    try:
        hours = int(hours)
    except (ValueError, TypeError):
        return "Please enter a valid number", 400

    user = users_collection.find_one({"name": username})
    game = games_collection.find_one({"name": game_name})

    if not user or not game:
        return "User or game not found.", 404

    play_log = user.get("play_log", {})
    play_log[game_name] = play_log.get(game_name, 0) + hours

    users_collection.update_one({"name": username}, {
        "$set": {
            "play_log": play_log,
            "total_play_time": user["total_play_time"] + hours,
            "most_played_game": max(play_log, key=play_log.get)
        }
    })

    games_collection.update_one({"name": game_name}, {"$inc": {"play_time": hours}})
    return redirect(url_for('user_page', name=username))


@app.route('/rate_game', methods=['POST'])
def rate_game():
    username = request.form.get('username')
    game_name = request.form.get('game_name')
    rating = request.form.get('rating')

    if not username or not game_name or not rating:
        return "All fields are required.", 400

    rating = int(rating)

    user = users_collection.find_one({"name": username})
    game = games_collection.find_one({"name": game_name})
    if not user or not game:
        return "User or game not found.", 404
    
    if not game.get("enable_comments", True):
        return "Rating is disabled for this game.", 403

    if user.get("play_log", {}).get(game_name, 0) < 1:
        return "You need to play at least 1 hour to rate.", 403

    ratings = user.get("ratings", {})
    ratings[game_name] = rating

    average = sum(ratings.values()) / len(ratings)
    users_collection.update_one({"name": username}, {"$set": {"ratings": ratings, "average_rating": average}})

    all_users = users_collection.find({"ratings." + game_name: {"$exists": True}})
    total_weighted, total_play = 0, 0
    for u in all_users:
        t = u.get("play_log", {}).get(game_name, 0)
        r = u.get("ratings", {}).get(game_name, 0)
        total_weighted += t * r
        total_play += t

    new_rating = total_weighted / total_play if total_play > 0 else 0
    games_collection.update_one({"name": game_name}, {"$set": {"rating": new_rating}})
    return redirect(url_for('user_page', name=username))


@app.route('/comment_game', methods=['POST'])
def comment_game():
    username = request.form.get("username")
    game_name = request.form.get("game_name")
    comment = request.form.get("comment")

    if not username or not game_name or not comment:
        return "All fields are required.", 400
    
    if not game.get("enable_comments", True):
        return "Commenting is disabled for this game.", 403

    user = users_collection.find_one({"name": username})
    game = games_collection.find_one({"name": game_name})
    if not user or not game:
        return "user or game not found.", 404

    if user.get("play_log", {}).get(game_name, 0) < 1:
        return "You need to play at least 1 hour to comment.", 403

    updated_comments = [c for c in user["comments"] if c["game"] != game_name]
    updated_comments.append({"game": game_name, "text": comment})
    users_collection.update_one({"name": username}, {"$set": {"comments": updated_comments}})

    updated_game_comments = [c for c in game["all_comments"] if c["user"] != username]
    updated_game_comments.append({
        "user": username,
        "text": comment,
        "play_time": user["play_log"][game_name]
    })
    updated_game_comments.sort(key=lambda c: c["play_time"], reverse=True)
    games_collection.update_one({"name": game_name}, {"$set": {"all_comments": updated_game_comments}})
    return redirect(url_for('games_page', name=game_name))


@app.route('/add_sample_game')
def add_sample_game():
    example_game = {
        "name": "Mystery Island",
        "genres": ["Adventure", "Puzzle"],
        "photo": "https://via.placeholder.com/200",
        "play_time": 0,
        "rating": 0,
        "all_comments": [],
        "enable_comments": True
    }
    games_collection.insert_one(example_game)
    return "Sample game added successfully!"


@app.route('/add_game_form', methods=['GET'])
def add_game_form_page():
    return render_template("add_game.html")


@app.route('/add_game_form', methods=['POST'])
def add_game_form_submit():
    name = request.form.get('name')
    genres = request.form.get('genres')
    photo = request.form.get('photo')
    developer = request.form.get('developer')
    release_date = request.form.get('release_date')
    info = request.form.get('optional1')

    if not name or not genres or not photo or not developer or not release_date:
        return "Required fields are empty.", 400

    game = {
        "name": name,
        "genres": [g.strip() for g in genres.split(',')],
        "photo": photo,
        "developer": developer,
        "release_date": release_date,
        "play_time": 0,
        "rating": 0,
        "all_comments": [],
        "enable_comments": True
    }

    if info:
        game["optional1"] = info

    games_collection.insert_one(game)
    return redirect(url_for('games_page'))


@app.route('/play_game_form')
def play_game_form():
    return render_template('play_game.html')  # dosya adı bu olacak


@app.route('/remove_user_form', methods=['GET'])
def remove_user_form_page():
    return render_template("remove_user.html")


@app.route('/remove_user_form', methods=['POST'])
def remove_user_form_submit():
    name = request.form.get('name')
    if not name:
        return "User name is required.", 400

    user = users_collection.find_one({"name": name})
    if not user:
        return f"No user named '{name}' found!", 404

    # Kullanıcının etkilerini oyunlardan kaldır
    ratings = user.get("ratings", {})
    play_log = user.get("play_log", {})
    comments = user.get("comments", [])

    for game_name in play_log:
        games_collection.update_one({"name": game_name}, {"$inc": {"play_time": -play_log[game_name]}})

    for game_name in ratings:
        # Oyunun puanlamasını yeniden hesapla
        all_users = list(users_collection.find({"ratings." + game_name: {"$exists": True}, "name": {"$ne": name}}))
        total_weighted = 0
        total_play = 0
        for u in all_users:
            t = u.get("play_log", {}).get(game_name, 0)
            r = u.get("ratings", {}).get(game_name, 0)
            total_weighted += t * r
            total_play += t
        new_rating = total_weighted / total_play if total_play else 0
        games_collection.update_one({"name": game_name}, {"$set": {"rating": new_rating}})

    for c in comments:
        games_collection.update_one({"name": c["game"]}, {
            "$pull": {"all_comments": {"user": name}}
        })

    users_collection.delete_one({"name": name})
    return f"User '{name}' and their data removed. <br><a href='/'>← Ana Sayfa</a>"

@app.route('/toggle_comment_form', methods=['POST'])
def toggle_comment_form_submit():
    name = request.form.get("name")
    action = request.form.get("action")
    if not name or not action:
        return "All fields are required", 400

    if action == "enable":
        games_collection.update_one({"name": name}, {"$set": {"enable_comments": True}})
        return f"Comments and ratings enabled for '{name}' <br><a href='/'>← Ana Sayfa</a>"
    elif action == "disable":
        games_collection.update_one({"name": name}, {"$set": {"enable_comments": False}})
        return f"Comments and ratings disabled for '{name}' <br><a href='/'>← Ana Sayfa</a>"
    else:
        return "Invalid action", 400