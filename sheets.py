import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CRED_PATH = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH")
creds = Credentials.from_service_account_file(CRED_PATH, scopes=SCOPES)
gc = gspread.authorize(creds)
SHEET_ID = os.getenv("SHEET_ID")

def sheet_append_row(row):
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1
    # create row array in the expected order:
    values = [
      row['product_id'],
      row['main_photo'],
      row['additional_photos'],
      row['title'],
      row['description'],
      row['type_l1'],
      row['category_l2'],
      row['color'],
      row['gender'],
      row['brand'],
      row['supplier'],
      row['full_price'] and f"{row['full_price']/100:.2f}" or "",
      row['discounted_price'] and f"{row['discounted_price']/100:.2f}" or "",
      "TRUE" if row['needs_review'] else "FALSE"
    ]
    ws.append_row(values, value_input_option='USER_ENTERED')

def write_row_to_sheet(row):
    try:
        sheet_append_row(row)
    except Exception as e:
        # add robust logging & retry here
        raise
