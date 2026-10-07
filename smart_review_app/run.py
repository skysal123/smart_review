from app import create_app, db
from app.models import Business, Product
import os

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Seed data for testing if empty
        if not Business.query.first():
            b1 = Business(name="The Gourmet Cafe", google_place_id="ChIJN1S_EXAMPLE_ID")
            db.session.add(b1)
            db.session.commit()

            p1 = Product(name="Cappuccino", business_id=b1.id)
            p2 = Product(name="Avocado Toast", business_id=b1.id)
            p3 = Product(name="Blueberry Muffin", business_id=b1.id)
            db.session.add_all([p1, p2, p3])
            db.session.commit()
            print("Database seeded with test data!")

    app.run(debug=True, host='0.0.0.0', port=5000)
