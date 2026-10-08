from app import db

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))
    google_place_id = db.Column(db.String(255), nullable=False)
    qr_code_path = db.Column(db.String(255))
    tone = db.Column(db.String(50), default='professional')
    products = db.relationship('Product', backref='business', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
