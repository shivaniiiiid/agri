from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.base import AdminIndexView
from flask_login import current_user
from flask import redirect, url_for
from app import db
from models import User, Product, Auction, Bid, Transaction

# Custom base model view with authentication
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=url_for('admin.index')))

# Custom admin index view with authentication
class SecureAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=url_for('admin.index')))

# Custom model views
class UserModelView(SecureModelView):
    column_list = ('id', 'username', 'email', 'first_name', 'last_name', 'is_farmer', 'is_admin', 'created_at')
    column_searchable_list = ('username', 'email', 'first_name', 'last_name')
    column_filters = ('is_farmer', 'is_admin', 'created_at')
    form_excluded_columns = ('password_hash',)
    can_create = False  # Disable creation through admin (use registration instead)
    
    def on_model_change(self, form, model, is_created):
        # Prevent changing admin status of self
        if not is_created and model.id == current_user.id and not model.is_admin:
            model.is_admin = True

class ProductModelView(SecureModelView):
    column_list = ('id', 'name', 'category', 'description')
    column_searchable_list = ('name', 'category')
    column_filters = ('category',)

class AuctionModelView(SecureModelView):
    column_list = ('id', 'title', 'base_price', 'current_price', 'start_time', 'end_time', 'is_active')
    column_searchable_list = ('title', 'description')
    column_filters = ('is_active', 'start_time', 'end_time')
    
    # Display relationships
    column_formatters = {
        'owner.username': lambda v, c, m, p: m.owner.username if m.owner else '',
        'product.name': lambda v, c, m, p: m.product.name if m.product else ''
    }

class BidModelView(SecureModelView):
    column_list = ('id', 'amount', 'created_at')
    column_searchable_list = []
    column_filters = ('created_at',)

class TransactionModelView(SecureModelView):
    column_list = ('id', 'amount', 'status', 'payment_method', 'created_at')
    column_searchable_list = []
    column_filters = ('status', 'payment_method', 'created_at')

def setup_admin(app):
    # Initialize Admin
    admin = Admin(
        app, 
        name='Agri-Auction Admin', 
        template_mode='bootstrap4',
        index_view=SecureAdminIndexView()
    )
    
    # Add model views
    admin.add_view(UserModelView(User, db.session))
    admin.add_view(ProductModelView(Product, db.session))
    admin.add_view(AuctionModelView(Auction, db.session))
    admin.add_view(BidModelView(Bid, db.session))
    admin.add_view(TransactionModelView(Transaction, db.session))
    
    return admin
