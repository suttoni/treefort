#tut 5
from app import app, db, lm, oid, nav
from flask import render_template, flash, redirect, session, url_for, request, g, jsonify
from flask.ext.login import login_user, logout_user, current_user, login_required
from datetime import datetime
from .forms import LoginForm, EditForm, PostForm, MessageForm
from .models import User, Post, Message, LeafsTaken
from config import POSTS_PER_PAGE,  MSGS_PER_PAGE
import math
import twilio.twiml

#navigation bar
nav.Bar('top', [
    nav.Item('Home', 'index'),
    nav.Item('Login', 'login')
])

## Aug 2, Fix User is alreadu following bug when you've already sent an offer
@app.route('/compose', methods=['GET', 'POST'])
@app.route('/compose/<string:nickname>/<int:id>', methods=['GET', 'POST'])
@login_required
def compose(nickname=None, id=None):
    form = MessageForm()
    replyMsg=0
    # cannot make offer to someone already following
    #if (id > 0):
    #    replyMsg = Message.query.filter(Message.id==id)
    print(nickname)
    if nickname is not None:
        form.nickname.data = nickname
    elif nickname is None and request.args.get('nickname') is not None:
        form.nickname.data = request.args.get('nickname')

    if form.validate_on_submit():
        user_id = g.user.find_user_Id(form.nickname.data)
        print(user_id)         #DEBUGGING LINE

        if user_id > 0:
            msg = Message(subject=form.subject.data, body=form.body.data,
                          timestamp=datetime.utcnow(), author=g.user, 
                          to_id=user_id, from_id=g.user.id, offer=form.leafs.data)   

            find_conn = LeafsTaken.query.filter((user_id == LeafsTaken.reciever_id and
                            g.user.id == LeafsTaken.sender_id)).first()       
            #if find_conn is not None and not math.isnan(form.leafs.data):
            # BROKEN forms.leaf.data
            if find_conn is None and form.leafs.data > 0:
                if g.user.current_leafs-form.leafs.data >= 0:
                    leaf_offer = LeafsTaken(reciever_id=user_id, sender_id=g.user.id,
                                            leafs_taken=form.leafs.data) 
                    print("LEAFS: ")
                    print(form.leafs.data)
                    g.user.current_leafs = g.user.current_leafs - form.leafs.data
                    print("Got HEre")
                    db.session.add(leaf_offer)
                    db.session.add(msg) 
                    db.session.commit()
                    flash('Your offer was sent!')
                else:
                    flash('Cannot complete offer.  Not enough leafs!')
            elif find_conn is not None and form.leafs.data > 0:
                flash ('An offer was already sent or user may already be following')
            else:
                db.session.add(msg) 
                db.session.commit()
                flash('Your message was sent!')
##### ADD CURRENT LEAF REMOVAL #####
##### SHOULD BE ABLE TO CANCEL REQUESTS ###
        else:
            flash('No user by that nickname exists!')
        return redirect(url_for('compose')) 
    #print(replyMsg)
    return render_template('compose.html',
        title='Compose',
        form=form,
        reply=replyMsg)

# ADD TO INBOX ANSWERS 
# ADD BACK current leafs to user who offered leafs when message is deleteds
@app.route('/inbox/<int:page>/id=<int:id>', methods=['GET', 'POST'])
@app.route('/inbox/<int:page>', methods=['GET', 'POST'])
@app.route('/inbox', methods=['GET'])
@login_required
def inbox(page=1, id=-1):
    #Debugging
    #Aug 3, problem with find_conn being None and sender referencing 
    if id > 0:
        msg = Message.query.get(id)
        print(msg)

        #Delete only offers not conversation messages
        if msg.offer > 0:
            find_conn = LeafsTaken.query.filter((msg.from_id == LeafsTaken.sender_id and
                        msg.to_id == LeafsTaken.reciever_id)).first()
            sender = User.query.filter(User.id == msg.from_id).first()

            sender.current_leafs = find_conn.leafs_taken + sender.current_leafs
            db.session.delete(find_conn)
            db.session.commit()

        db.session.delete(msg)
        db.session.commit()
        flash('Message was deleted!')
    messages = g.user.get_messages().paginate(page, MSGS_PER_PAGE, False)
    return render_template('inbox.html',
                            title='Inbox',
                            messages=messages)

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@app.route('/index/<int:page>', methods=['GET', 'POST'])
@login_required
def index(page=1):
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, timestamp=datetime.utcnow(), author=g.user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    posts = g.user.followed_posts().paginate(page, POSTS_PER_PAGE, False)
    print posts

    return render_template('index.html',
                           title='Home',
                           form=form,
                           posts=posts)
#tut 5

@app.route('/login', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        session['remember_me'] = form.remember_me.data
        return oid.try_login(form.openid.data, ask_for=['nickname', 'email'])
    return render_template('login.html', 
                           title='Sign In',
                           form=form,
                           providers=app.config['OPENID_PROVIDERS'])

@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()

@oid.after_login
def after_login(resp):
    if resp.email is None or resp.email == "":
        flash('Invalid login. Please try again.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=resp.email).first()
    if user is None:
        nickname = resp.nickname
        if nickname is None or nickname == "":
            nickname = resp.email.split('@')[0]
        nickname = User.make_unique_nickname(nickname)

#### RECENTLY CHANGED 7:22 PM!
        user = User(nickname=nickname, email=resp.email, 
                    current_leafs=15, leafs=15)
###############################

        db.session.add(user)
        db.session.commit()
        # make the user follow him/herself
        db.session.add(user.follow(user))
        db.session.commit()
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember=remember_me)
    return redirect(request.args.get('next') or url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))



#Tut 6
@app.route('/user/<nickname>')
@app.route('/user/<nickname>/<int:page>')
@login_required
def user(nickname, page=1):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('index'))
    posts = user.posts.paginate(page, POSTS_PER_PAGE, False)
    return render_template('user.html',
                           user=user,
                           posts=posts)

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    form = EditForm(g.user.nickname)
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.about_me = form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    elif request.method != "POST":
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me
    return render_template('edit.html', form=form)


# Aug 3, Remove offers in inbox if followed outside of inbox
@app.route('/follow/<nickname>')
@login_required
def follow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t follow yourself!')
        return redirect(url_for('user', nickname=nickname))
    u = g.user.follow(user)
    if u is None:
        flash('Cannot follow ' + nickname + '.')
        return redirect(url_for('user', nickname=nickname))
    offered = LeafsTaken.query.filter((user.id == LeafsTaken.sender_id and 
                             g.user.id == LeafsTaken.reciever_id)).first()
    #section checks to see if an offer exists if not add 2 leafs
    if offered is not None and offered.leafs_taken > 0:
        user.leafs = user.leafs - offered.leafs_taken
        g.user.leafs = g.user.leafs + offered.leafs_taken 
        g.user.current_leafs =g.user.current_leafs + offered.leafs_taken

        #Attempt to find offer from leafsTaken table to delete from inbox
        inbox_offer = Message.query.filter(
            Message.offer == offered.leafs_taken).first()
        db.session.delete(inbox_offer)
        db.session.commit()
    #### ADD TO LEAFTAKEN TABLE AS 2#######
    if offered is None:
        follow_leafs = LeafsTaken(reciever_id=g.user.id, sender_id=user.id,
                                 leafs_taken=-1)
        g.user.leafs = g.user.leafs+2
        g.user.current_leafs = g.user.current_leafs+2
        db.session.add(follow_leafs)
    #################################################
    db.session.add(u)
    db.session.commit()
    flash('You are now following ' + nickname + '!')
    return redirect(url_for('user', nickname=nickname))


###### FIX THIS TO WHERE IF YOU UNFOLLOW YOU CHECK LEAFTAKEN TABLE
@app.route('/unfollow/<nickname>')
@login_required
def unfollow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t unfollow yourself!')
        return redirect(url_for('user', nickname=nickname))
    u = g.user.unfollow(user)
    if u is None:
        flash('Cannot unfollow ' + nickname + '.')
        return redirect(url_for('user', nickname=nickname))

@app.route('/inbox/refresh')
def refresh():
    a = request.args.get('a', 0, type=int)
    return jsonify(result=a+1)


#############
# query leafTaken and see if it was a 2+ or offer CHANGE g.user.id and user.id with each other!!!!!
    find_conn = LeafsTaken.query.filter((g.user.id == LeafsTaken.reciever_id and 
                             user.id == LeafsTaken.sender_id)).first()
#return leafs accordingly
#############
    if find_conn.leafs_taken == -1 and g.user.current_leafs-2 >= 0:
        g.user.current_leafs = g.user.current_leafs - 2
        g.user.leafs = g.user.leafs - 2
        db.session.add(u)
        db.session.delete(find_conn)
        db.session.commit()
        flash('You have stopped following ' + nickname + '.')

    elif g.user.current_leafs-find_conn.leafs_taken >= 0:
        g.user.current_leafs = g.user.current_leafs -find_conn.leafs_taken
        g.user.leafs =g.user.leafs - find_conn.leafs_taken

        user.current_leafs = user.current_leafs + find_conn.leafs_taken
        user.leafs = user.leafs + find_conn.leafs_taken

        db.session.add(u)
        db.session.delete(find_conn)
        db.session.commit()
        flash('You have stopped following ' + nickname + '.')
    else:
        flash('You don\'t have ', {{find_conn.leafs_taken}}, ' leafs to unfollow' + nickname + '.')
    return redirect(url_for('user', nickname=nickname))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
