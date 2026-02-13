import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import jsonify
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blog_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Database Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True, default="ရုပ်ရှင်ဝါသနာအိုးတစ်ယောက်။") # ဒါလေးထည့်ပါ
    profile_pic = db.Column(db.String(100), default='default.jpg')
    posts = db.relationship('Post', backref='author', lazy=True)
    facebook = db.Column(db.String(120), nullable=True)
    telegram = db.Column(db.String(120), nullable=True)
    cover_pic = db.Column(db.String(100), nullable=False, default='default_cover.jpg')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # ဤစာကြောင်း ထည့်ရန်
    media_file = db.Column(db.String(100), nullable=True) 
    date_posted = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), default='General') # ဤစာကြောင်းကို ထည့်ပါ
    likes = db.relationship('PostLike', backref='post', cascade="all, delete-orphan", lazy=True)


class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # အကြောင်းကြားစာ လက်ခံမယ့်သူ
    sender_id = db.Column(db.Integer, nullable=False) # Like လုပ်တဲ့သူ
    sender_name = db.Column(db.String(50), nullable=False)
    post_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('User', backref=db.backref('notifications', lazy=True))

# Database Table ဆောက်ခြင်း
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def index():
    cat_name = request.args.get('category')
    
    query = Post.query
    if cat_name:
        query = query.filter_by(category=cat_name)
        
    posts = query.order_by(Post.date_posted.desc()).all()
    return render_template('index.html', posts=posts, current_category=cat_name)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        
        # Media File ဖမ်းယူခြင်း
        file = request.files.get('media_file')
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # static/uploads folder ထဲ သိမ်းမယ် (folder မရှိရင် ဆောက်ထားပါ)
            file.save(os.path.join('static/uploads', filename))
        
        new_post = Post(title=title, content=content, category=category, 
                        media_file=filename, author=current_user)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('create_post.html')

@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', post=post)


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author == current_user:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.bio = request.form.get('bio')
        current_user.facebook = request.form.get('facebook')
        current_user.telegram = request.form.get('telegram')
        file = request.files.get('profile_pic')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_pic = filename
        if 'cover_pic' in request.files:
            file = request.files['cover_pic']
            if file.filename != '':
                cover_fn = str(current_user.id) + "_cover_" + file.filename
                file.save(os.path.join(app.root_path, 'static/profile_pics', cover_fn))
                current_user.cover_pic = cover_fn
        db.session.commit()
        return redirect(url_for('user_profile', username=current_user.username))
    return render_template('edit_profile.html')


@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    # Like လုပ်ထားခြင်း ရှိ/မရှိ စစ်ဆေးတဲ့ logic
    # ... (မင်းရဲ့ အရင် like logic) ...
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if like:
        db.session.delete(like) # Like ပြန်ဖြုတ်မယ်
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like) # Like ပေးမယ်
    # Notification ပို့ရန် (ပိုင်ရှင်ကိုယ်တိုင် မဟုတ်မှသာ)
    if post.user_id != current_user.id:
        new_notif = Notification(
            user_id=post.user_id,
            sender_id=current_user.id,
            sender_name=current_user.username,
            post_id=post.id,
            message=f"{current_user.username} က မင်းရဲ့ '{post.title}' ကို Like လုပ်ခဲ့ပါတယ်။"
        )
        db.session.add(new_notif)
        db.session.commit()
    return redirect(request.referrer)


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/user/<string:username>')
def user_profile(username):
    # Username နဲ့ User ကို ရှာမယ်
    user = User.query.filter_by(username=username).first_or_404()
    # အဲဒီ User တင်ထားတဲ့ Post တွေကိုပဲ ပြန်ထုတ်မယ်
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).all()
    return render_template('user_profile.html', user=user, posts=posts)

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # ပိုင်ရှင်ဟုတ်မဟုတ် စစ်မယ်
    if post.author != current_user:
        flash("ဒီစာမူကို ပြင်ဆင်ခွင့်မရှိပါ!", "danger")
        return redirect(url_for('post', post_id=post.id))
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.category = request.form.get('category')
        
        # ပုံအသစ်တင်ရင် လဲပေးမယ်
        if 'media_file' in request.files:
            file = request.files['media_file']
            if file.filename != '':
                fn = str(post.id) + "_" + file.filename
                file.save(os.path.join(app.root_path, 'static/uploads', fn))
                post.media_file = fn
                
        db.session.commit()
        flash("စာမူကို ပြင်ဆင်ပြီးပါပြီ!", "success")
        return redirect(url_for('post', post_id=post.id))
        
    return render_template('edit_post.html', post=post)

@app.route('/live_search')
def live_search():
    query = request.args.get('q', '')
    if query:
        # Title ထဲမှာ ပါတဲ့စာသားကို ရှာမယ်
        posts = Post.query.filter(Post.title.ilike(f'%{query}%')).limit(5).all()
        results = []
        for post in posts:
            results.append({
                'id': post.id,
                'title': post.title,
                'image': url_for('static', filename='uploads/' + post.media_file) if post.media_file else url_for('static', filename='uploads/default.jpg')
            })
        return jsonify(results)
    return jsonify([])

@app.route('/notifications')
@login_required
def notifications():
    # User ရဲ့ notification အားလုံးကို ဖတ်ပြီးသား (is_read = True) အဖြစ် ပြောင်းပေးမယ်
    notifs = Notification.query.filter_by(user_id=current_user.id).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('notifications.html')

if __name__ == '__main__':
    app.run()