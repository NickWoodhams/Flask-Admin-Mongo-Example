from flask import Flask, url_for, redirect, render_template, request
from flask.ext.mongoengine import MongoEngine

from wtforms import form, fields, validators

from flask.ext import admin, login
from flask.ext.admin.contrib.mongoengine import ModelView
from flask.ext.admin import Admin, BaseView, AdminIndexView, expose
from flask.ext.admin.form import rules
from flask.ext.admin import helpers

# Create application
app = Flask(__name__)

# Create dummy secrey key so we can use sessions
app.config['SECRET_KEY'] = '123456790'

# MongoDB settings
app.config['MONGODB_SETTINGS'] = {'DB': 'test'}
db = MongoEngine()
db.init_app(app)


# Create user model. For simplicity, it will store passwords in plain text.
# Obviously that's not right thing to do in real world application.
class User(db.Document):
    login = db.StringField(max_length=80, unique=True)
    email = db.StringField(max_length=120)
    password = db.StringField(max_length=64)

    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    # Required for administrative interface
    def __unicode__(self):
        return self.login


# Define login and registration forms (for flask-login)
class LoginForm(form.Form):
    login = fields.TextField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        if user.password != self.password.data:
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        return User.objects(login=self.login.data).first()


class RegistrationForm(form.Form):
    login = fields.TextField(validators=[validators.required()])
    email = fields.TextField()
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        if User.objects(login=self.login.data):
            raise validators.ValidationError('Duplicate username')


class SearchField(db.Document):
        name = db.StringField(required=True, unique=True)
        label = db.StringField(required=True)

        def __unicode__(self):
                return str(self.label)


class SearchType(db.Document):
        source = db.StringField(
            required=True,
            unique_with='label',
            choices=['database',
                     'external'])
        label = db.StringField(
            required=True,
            unique_with='endpoint')
        required_fields = db.ListField(
            db.ReferenceField(
                'SearchField', reverse_delete_rule=db.PULL))
        optional_fields = db.ListField(
            db.ReferenceField('SearchField', reverse_delete_rule=db.PULL))
        endpoint = db.StringField(required=True)

        def __unicode__(self):
                return str(self.label)


class Product(db.Document):
        active = db.BooleanField(default=False)
        name = db.StringField(required=True)
        price = db.DecimalField(precision=2)
        searchType = db.ListField(
            db.ReferenceField('SearchType',
                              reverse_delete_rule=db.PULL))
        params = db.ListField(db.ReferenceField('SearchField'))

        def __unicode__(self):
                return str(self.name)


# Initialize flask-login
def init_login():
    login_manager = login.LoginManager()
    login_manager.setup_app(app)

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):
        return User.objects(id=user_id).first()


# Create customized model view class
class MyModelView(ModelView):

    def is_accessible(self):
        return login.current_user.is_authenticated()


# Create customized index view class
class MyAdminIndexView(admin.AdminIndexView):

    def is_accessible(self):
        return login.current_user.is_authenticated()


# Customized admin views
class UserView(ModelView):
    column_filters = ['name']

    column_searchable_list = ('name', 'password')

    form_ajax_refs = {
        'tags': {
            'fields': ('name',)
        }
    }


class TodoView(ModelView):
    column_filters = ['done']

    form_ajax_refs = {
        'user': {
            'fields': ['name']
        }
    }


class PostView(ModelView):
    form_subdocuments = {
        'inner': {
            'form_subdocuments': {
                None: {
                    # Add <hr> at the end of the form
                    'form_rules': ('name', 'tag', 'value', rules.HTML('<hr>')),
                    'form_widget_args': {
                        'name': {
                            'style': 'color: red'
                        }
                    }
                }
            }
        }
    }


class ProductView(BaseView):
    @expose('/')
    def index(self):
        # Sitdown counts
        search_types = SearchType.objects

        return self.render(
            'admin/productview.html',
            search_types=search_types)


# Flask views
@app.route('/')
def index():
    return render_template('index.html', user=login.current_user)


@app.route('/login/', methods=('GET', 'POST'))
def login_view():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        user = form.get_user()
        login.login_user(user)
        return redirect(url_for('index'))

    return render_template('form.html', form=form)


@app.route('/register/', methods=('GET', 'POST'))
def register_view():
    form = RegistrationForm(request.form)
    if request.method == 'POST' and form.validate():
        user = User()

        form.populate_obj(user)
        user.save()

        login.login_user(user)
        return redirect(url_for('index'))

    return render_template('form.html', form=form)


@app.route('/logout/')
def logout_view():
    login.logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Initialize flask-login
    init_login()

    # Create admin
    admin = admin.Admin(app, 'Auth', index_view=MyAdminIndexView())

    # Add view
    admin.add_view(MyModelView(User))
    admin.add_view(ModelView(SearchField))
    admin.add_view(ModelView(SearchType))
    admin.add_view(ProductView(Product))

    # Start app
    app.run(debug=True)
