from flask import Flask, render_template, request, redirect, session, url_for
import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
from connect_contract import w3, contract, abi, contract_bytecode

app = Flask(__name__)
app.secret_key = "cf_edi_s6_g3_5_ai_b"
wallet_private_key = ''

# Initialize Firebase Admin SDK
cred = credentials.Certificate("crowdfunding-platform-ceab9-firebase-adminsdk-klmj2-fae3aaaa91.json")
firebase_admin.initialize_app(cred, {'storageBucket': 'crowdfunding-platform-ceab9.appspot.com'})

cl = firestore.client()

@app.route('/')
def hello():
    campaigns = fetch_campaigns_from_firestore()
    return render_template('home.html', campaigns=campaigns)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user_name = request.form.get('user_name')
        email = request.form.get('email')
        institution = request.form.get('institution')
        password = request.form.get('password')
        mobile = request.form.get('mobile')
        # user_type = request.form.get('user_type')

        try:
            user = auth.create_user(email=email, password=password)
            # Store user information in Firestore
            user_doc_ref = cl.collection('users').document(user.uid)
            user_doc_ref.set({
                'user_name': user_name,
                'email': email,
                'institution': institution,
                'mobile': mobile,
                'wallet_address': ''
                # 'user_type': user_type
            })
            session['user_email'] = email
            return redirect(url_for('login'))
        except ValueError as e:
            error_message = e.message
            return render_template('signup.html', error=error_message)
    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            user = auth.get_user_by_email(email)            
            session['user_email'] = email
            print(email)
            return redirect(url_for('home'))
        except Exception as e:
            error_message = str(e)
            return render_template('login.html', error=error_message)
    else:
        return render_template('login.html')

@app.route('/is_logged_in', methods=['GET'])
def is_logged_in():
    user_email = session.get('user_email')
    if user_email:
        return {'logged_in': True, 'user_email': user_email}
    else:
        return {'logged_in': False}

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('login'))

    
def calculate_progress(raised, target):
    return (float(raised) / float(target)) * 100

def fetch_user_details_from_firestore(email):
    user = auth.get_user_by_email(email)
    user_id = user.uid
    user_doc = cl.collection('users').document(user_id).get().to_dict()
    print(user_doc)

    return user_doc

@app.route('/update_wallet', methods=['POST'])
def update_wallet():
    if 'user_email' not in session:
        return {'error': 'User not logged in'}, 403

    wallet_address = request.json.get('wallet_address')
    user_email = session['user_email']
    try:
        user = auth.get_user_by_email(user_email)
        user_id = user.uid
        user_doc_ref = cl.collection('users').document(user_id)
        user_doc_ref.update({'wallet_address': wallet_address})

        return {'success': True}
    except Exception as e:
        print(f"Error updating wallet address: {e}")
        return {'error': str(e)}, 500

def fetch_campaigns_from_firestore():
    campaigns = []
    campaign_ref = cl.collection('campaigns')
    docs = campaign_ref.stream()

    for doc in docs:
        campaign_data = doc.to_dict()
        campaigns.append({
            'name': campaign_data['campaign_name'],
            # 'description': campaign_data['campaign_description'],
            'image': campaign_data['image_input'],
            'progress': calculate_progress(campaign_data['collectedAmount'], campaign_data['target_amount']),
            'min_contribution': campaign_data['min_contribution'],
            'target_amount': campaign_data['target_amount'],
            # 'owner_address': campaign_data['owner_address'],
            # 'second_owner_address': campaign_data['second_owner_address'],
            # 'contract_address': campaign_data['contract_address']
        })
    return campaigns

@app.route('/homepage')
def home():
    campaigns = fetch_campaigns_from_firestore()
    return render_template('home.html', campaigns=campaigns)

@app.route('/user_profile')
def profile():
    email = session.get('user_email')
    return render_template('profile.html', user=fetch_user_details_from_firestore(email=email))

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
            'progress': calculate_progress(campaign_data['collectedAmount'], campaign_data['target_amount']),
            'min_contribution': campaign_data['min_contribution'],
            'target_amount': campaign_data['target_amount'],
            'owner_address': campaign_data['owner_address'],
            'second_owner_address': campaign_data['second_owner_address'],
            'contract_address': campaign_data['contract_address'],
            'collectedAmount': campaign_data['collectedAmount']
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
        owner_address = request.form['fowner_address']

        owner_address = w3.to_checksum_address(owner_address)
        second_owner_address = w3.to_checksum_address(second_owner_address)
        # Upload image to Storage
        if image:
            bucket = storage.bucket()
            blob = bucket.blob(campaign_name)
            blob.upload_from_string(image.read(), content_type=image.content_type)
            blob.make_public()
            img_url = blob.public_url
        else:
            img_url = None

        
        gas_price = w3.eth.gas_price
        transaction = contract.constructor(second_owner_address, w3.to_wei(target_amount, 'ether'), w3.to_wei(min_amt, 'ether')).build_transaction({
            'from': owner_address,
            'nonce': w3.eth.get_transaction_count(owner_address),
            'gas': 6721975,
            'gasPrice': gas_price
        })

        signed_txn = w3.eth.account.sign_transaction(transaction, wallet_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(tx_receipt)
        # TODO: along with printing receipt, make provision such that user can download a pdf of that receipt.

        # Store data into Firestore
        doc_ref = cl.collection('campaigns').document(tx_receipt.contractAddress)
        doc_ref.set({
            'min_contribution': min_amt,
            'campaign_name': campaign_name,
            'campaign_description': campaign_description,
            'image_input': img_url,
            'target_amount': target_amount,
            'second_owner_address': second_owner_address,
            'owner_address': owner_address,
            'contract_address': tx_receipt.contractAddress,
            'collectedAmount': 0
        })
        
        return redirect(url_for('home'))
    
@app.route('/donate/<campaign_name>', methods=['POST'])
def donate(campaign_name):
    email = session.get('user_email')
    user_details = fetch_user_details_from_firestore(email=email)
    campaign_details_ = fetch_individual_campaign_from_firestore(campaign_name=campaign_name)

    donor_address = user_details['wallet_address']
    donor_address = w3.to_checksum_address(donor_address)
    donation_amount = request.form['donation_amount']

    contract_ = w3.eth.contract(address=campaign_details_['contract_address'], abi=abi, bytecode=contract_bytecode)

    transaction = contract_.functions.donate().build_transaction({
        'from': donor_address,
        'value': w3.to_wei(donation_amount, 'ether'),
        'gas': 6721975,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(donor_address)
    })

    signed_txn = w3.eth.account.sign_transaction(transaction, wallet_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash,timeout=600)
    print(tx_receipt)
    # TODO: along with printing receipt, make provision such that user can download a pdf of that receipt.
    
    amount_collected = contract_.functions.amountCollected().call()    
    print("Amt Coll: ", amount_collected)
    doc_ref = cl.collection('campaigns').document(campaign_details_['contract_address'])
    doc_ref.update({
        'collectedAmount': str(w3.from_wei(amount_collected, 'ether'))
    })

    return redirect(url_for('home'))

@app.route('/withdraw_donation/<campaign_name>', methods=['POST'])
def withdraw_donation(campaign_name):
    email = session.get('user_email')
    user_details = fetch_user_details_from_firestore(email=email)
    campaign_details_ = fetch_individual_campaign_from_firestore(campaign_name=campaign_name)

    donor_address = user_details['wallet_address']
    contract_address = campaign_details_['contract_address']

    donor_address = w3.to_checksum_address(donor_address)
    contract_instance = w3.eth.contract(address=contract_address, abi=abi)

    transaction = contract_instance.functions.withdrawDonation().build_transaction({
        'from': donor_address,
        'gas': 6721975,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(donor_address)
    })

    signed_txn = w3.eth.account.sign_transaction(transaction, wallet_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(tx_receipt)
    # TODO: along with printing receipt, make provision such that user can download a pdf of that receipt.

    amount_collected = contract_instance.functions.amountCollected().call()    
    print("Amt Coll: ", amount_collected)
    doc_ref = cl.collection('campaigns').document(campaign_details_['contract_address'])
    doc_ref.update({
        'collectedAmount': str(w3.from_wei(amount_collected, 'ether'))
    })

    return redirect(url_for('home'))

    
if __name__ == '__main__':
    app.run(debug=True)