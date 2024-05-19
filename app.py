from flask import Flask, render_template, request, redirect, url_for
import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
import connect_contract

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Initialize Firebase Admin SDK
cred = credentials.Certificate("crowdfunding-platform-ceab9-firebase-adminsdk-klmj2-fae3aaaa91.json")
firebase_admin.initialize_app(cred, {'storageBucket': 'crowdfunding-platform-ceab9.appspot.com'})

cl = firestore.client()

@app.route('/')
def hello():
    campaigns = fetch_campaigns_from_firestore()
    return render_template('home.html', campaigns=campaigns)

# Route for rendering sign up form
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user_name = request.form.get('user_name')
        email = request.form.get('email')
        institution = request.form.get('institution')
        password = request.form.get('password')
        # user_type = request.form.get('user_type')

        try:
            user = auth.create_user(email=email, password=password)
            # auth.set_custom_user_claims(user.uid, {'user_type': user_type})
            # db.reference(f'/users/{user.uid}').update({'user_type': user_type, 'user_name': user_name, 'email': email})
            # Store user information in Firestore
            user_doc_ref = cl.collection('users').document(user.uid)
            user_doc_ref.set({
                'user_name': user_name,
                'email': email,
                'institution': institution,
                # 'user_type': user_type
            })
            # session['user_type'] = user_type

            return redirect(url_for('login'))
        except ValueError as e:
            error_message = e.message
            return render_template('signup.html', error=error_message)
    return render_template('signup.html')

# Route for user login
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        # password = request.json.get('password')
        print(email)

        try:
            # Sign in the user with email and password
            user = auth.get_user_by_email(email)
            # Store user's email in session
            # session['user_email'] = email
            # print("session email: "+session['user_email'])

            # print('User email: '+session['user_email'])

            # Retrieve user's ID from Firebase
            user_id = user.uid
            # session['user_id'] = user_id

            # Get user's information from Firestore using user ID
            user_doc = cl.collection('users').document(user_id).get().to_dict()

            # Store user's information in session
            # session['user_info'] = user_doc
            # session['user_type'] = user_doc.get('user_type')
            # print('User type: '+session['user_type'])

            # Redirect to get_details page upon successful login
            return redirect(url_for('home'))
        except Exception as e:
            # Handle sign-in errors
            error_message = str(e)
            return render_template('login.html', error=error_message)
        
    else:
        return render_template('login.html')
    
def calculate_progress(raised, target):
    return (int(raised) / int(target)) * 100

def fetch_campaigns_from_firestore():
    campaigns = []
    # Assuming you have a collection named 'campaigns' in Firestore
    campaign_ref = cl.collection('campaigns')
    docs = campaign_ref.stream()

    for doc in docs:
        campaign_data = doc.to_dict()
        campaigns.append({
            'name': campaign_data['campaign_name'],
            'description': campaign_data['campaign_description'],
            'image': campaign_data['image_input'],
            'progress': calculate_progress(campaign_data['min_contribution'], campaign_data['target_amount']),
            'min_contribution': campaign_data['min_contribution'],
            'target_amount': campaign_data['target_amount']
        })

    return campaigns

@app.route('/homepage')
def home():
    campaigns = fetch_campaigns_from_firestore()
    return render_template('home.html', campaigns=campaigns)

def fetch_individual_campaign_from_firestore(campaign_name):
    campaign_ref = cl.collection('campaigns')
    query = campaign_ref.where('campaign_name', '==', campaign_name).limit(1)
    docs = query.stream()

    for doc in docs:
        campaign_data = doc.to_dict()

        individual_campaign = {
            'name': campaign_data['campaign_name'],
            'description': campaign_data['campaign_description'],
            'image': campaign_data['image_input'],
            'progress': calculate_progress(campaign_data['min_contribution'], campaign_data['target_amount']),
            'min_contribution': campaign_data['min_contribution'],
            'target_amount': campaign_data['target_amount'],
            # 'second_owner_address':campaign_data['second_owner_address']
        }

        return individual_campaign

    return None  # Return None if no campaign with the given name is found


@app.route('/campaign/<campaign_name>')
def campaign_details(campaign_name):
    campaign = fetch_individual_campaign_from_firestore(campaign_name=campaign_name)
    print(campaign)
    return render_template('campaign_detail.html', campaign=campaign)

@app.route('/create_campaign')
def create_campaign():
    return render_template('create_campaign.html')

@app.route('/submit', methods=['POST'])
def add_campaign():
    if request.method == 'POST':
        min_amt = request.form['min_contribution']
        campaign_name = request.form['campaign_name']
        campaign_description = request.form['campaign_description']
        image = request.files['image_input']
        target_amount = request.form['target_amount']
        second_owner_address = request.form['sowner_address']

        # Upload image to Storage
        if image:
            bucket = storage.bucket()
            blob = bucket.blob(campaign_name)
            blob.upload_from_string(image.read(), content_type=image.content_type)
            blob.make_public()
            img_url = blob.public_url
        else:
            img_url = None
        

        # Store data into Firestore
        doc_ref = cl.collection('campaigns').document()
        doc_ref.set({
            'min_contribution': min_amt,
            'campaign_name': campaign_name,
            'campaign_description': campaign_description,
            'image_input': img_url,
            'target_amount': target_amount,
            'second_owner_address': second_owner_address
        })
        
        # return 'Campaign added to Firestore successfully.'
        return redirect(url_for('home'))
    
if __name__ == '__main__':
    app.run(debug=True)