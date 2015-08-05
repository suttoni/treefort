from app import db
from hashlib import md5

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id')))
#NEW CODE
#userMessage = db.Table('userMessage',
#    db.Column('message_id', db.Integer, db.ForeignKey('message.id')),
#    db.Column('user_id', db.Integer, db.ForeignKey('user.id')))

#messaging = db.Table('userMessage',
#    db.Column('messager_id', db.Integer, db.ForeignKey('user.id')),
#    db.Column('messaged_id', db.Integer, db.ForeignKey('user.id')))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(64), index=True, unique=True)
    
    # used for user statistics leafs or seeds?
    leafs = db.Column(db.Integer)
    current_leafs = db.Column(db.Integer)

    email = db.Column(db.String(120), index=True, unique=True)
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    messages = db.relationship('Message', backref='author', lazy='dynamic')
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime)
    followed = db.relationship('User', 
                               secondary=followers, 
                               primaryjoin=(followers.c.follower_id == id), 
                               secondaryjoin=(followers.c.followed_id == id), 
                               backref=db.backref('followers', lazy='dynamic'), 
                               lazy='dynamic')
    #NEW CODE
    #messaged = db.relationship('Message', secondary=userMessage, backref='author')

    #messaged = db.relationship('User', 
    #                           secondary=messaging, 
    #                           primaryjoin=(messaging.c.messager_id == id), 
    #                           secondaryjoin=(messaging.c.messaged_id == id), 
    #                           backref=db.backref('messaging', lazy='dynamic'), 
    #                           lazy='dynamic')

    @staticmethod
    def make_unique_nickname(nickname):
        if User.query.filter_by(nickname=nickname).first() is None:
            return nickname
        version = 2
        while True:
            new_nickname = nickname + str(version)
            if User.query.filter_by(nickname=new_nickname).first() is None:
                break
            version += 1
        return new_nickname

    def avatar(self, size):
        return 'http://www.gravatar.com/avatar/%s?d=mm&s=%d' % \
        (md5(self.email.encode('utf-8')).hexdigest(), size)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)  # python 2
        except NameError:
            return str(self.id)  # python 3

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
            return self

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
            return self

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0

    def followed_posts(self):
        pos = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
                followers.c.follower_id == self.id).order_by(
                    Post.timestamp.desc())
        #Debugging
        for p in pos:
            print (p.id, p.body)
        return pos
#NEW CODE
    #FUNCTION RETURNS ID of user with this nickname!
    def find_user_Id(self, nickname):
        usr = User.query.filter(User.nickname == nickname)
        for u in usr:
            if u != None: 
                return u.id
        return -1

    def get_messages(self):
        msg = Message.query.filter(Message.to_id == self.id).order_by(
                Message.timestamp.desc())
        # DEBUGGING
        for m in msg:
            print (m.id, m.to_id, m.from_id)
        return msg

    def __repr__(self):
        return '<User %r>' % (self.nickname)

#Add lifetime to have people answer to your posts
class Post(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # determines how long people have to answer
    lifetime = 3600

    def __repr__(self):
        return '<Post %r>' % (self.body)
#NEW CODE
class Message(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    subject = db.Column(db.String(30))
    body = db.Column(db.String(120))
    to_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime)
    lifetime = 30
    # maybe add a flag 
    offer = db.Column(db.Integer)
    from_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<Message %r>' % (self.body)

class LeafsTaken(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    reciever_id = db.Column(db.Integer)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    leafs_taken = db.Column(db.Integer)

    def __repr__(self):
        return '<leafsTaken %r>' % (self.leafs_taken)
