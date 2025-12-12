from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
import csv
from flask import Flask, request

app = Flask(__name__)


class Config:
    def __init__(self, login_url, enquiries_url, username, password):
        self.LOGIN_URL = login_url
        self.ENQUIRIES_URL = enquiries_url
        self.USERNAME = username
        self.PASSWORD = password


def get_page_info(config: Config):
    chrome_options = Options()
    service = Service()
    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("1. Chrome driver started")

        driver.get(config.LOGIN_URL)
        print(f"2. Navigated to login page: {config.LOGIN_URL}")

        wait = WebDriverWait(driver, 10)
        username_field = wait.until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        password_field = driver.find_element(By.NAME, "password")
        login_button = driver.find_element(By.NAME, 'submit')

        time.sleep(2)
        print("Logging in ...")
        username_field.send_keys(config.USERNAME)
        password_field.send_keys(config.PASSWORD)
        login_button.click()

        wait = WebDriverWait(driver, 3)

        print("Navigating to enquiries page..")

        print("applying filters")

        country_dropdown_element = wait.until(
            EC.presence_of_element_located((By.ID, "filterByCountry"))
        )
        country_select = Select(country_dropdown_element)
        country_select.select_by_value("India")
        print("   -> Selected value 'India' in the country filter.")

        print("Selction of date")
        date_input_trigger = wait.until(
            EC.element_to_be_clickable((By.ID, "filterByDate"))
        )
        date_input_trigger.click()
        print("Date Widget Opened")
        time.sleep(1)
        xpath_today_option = "/html/body/div[6]/div[1]/ul/li[3]"
        today_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath_today_option))
        )
        today_button.click()
        print("Today Option Clicked")

        print("Clicking on search button")
        search_button = wait.until(

            EC.element_to_be_clickable((By.ID, "applyFilterBtn"))
        )
        search_button.click()
        print("Clicked the **Search** button")

        print("loading all possible entries by scrolling")

        last_height = driver.execute_script("return document.body.scrollHeight")

        print(last_height)

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("   -> Page height did not change. All enquiries loaded.")
                break
            last_height = new_height
            print(f"   -> Scrolled and loaded more data. New height: {new_height}px.")

        time.sleep(5)
        print("10. Page fully loaded to the end.")

        return driver.page_source
    except Exception as e:
        print("An error occurred during the selenium execution: " + e)

    finally:
        if driver:
            time.sleep(5)
            driver.quit()

            print("browser session ended")


BS_CONFIG = {
    # Main repeating enquiry block
    'ENQUIRY_BLOCK_SELECTOR': "div.media.align-items-center.rounded.border.mb-3",

    # Block containing Date, Ref, Location (all in one <small> tag)
    'DETAILS_LINE_SELECTOR': "div.media-body p.text-body small",

    # Car Make/Model/Year link
    'CAR_LINE_SELECTOR': "div.media-body h6 a",

    # Part Name (The strong tag)
    'PART_NAME_SELECTOR': "div.media-body strong",

    # Part Condition (The small tag under the part name)
    'PART_CONDITION_SELECTOR': "div.media-body p.mb-0 small strong",

    # Phone/Call Button (Crucial: targets the button that has the onClick attribute)
    'PHONE_BTN_SELECTOR': "a[onClick*='tel:']",

    # WhatsApp Button (The second anchor tag in the contact link container)
    'WHATSAPP_BTN_SELECTOR': ".d-flex.justify-content-center a:nth-child(2)",

    # Email Link (Placeholder, as a direct mailto: link was not present)
    'EMAIL_LINK_SELECTOR': "a[href^='mailto:']",
}


def extract_data_from_html(html_source: str, bs_config: dict) -> list[dict]:
    if not html_source:
        print('No HTML is provided')
        return []
    print("Starting Beautiful Soup")
    soup = BeautifulSoup(html_source, 'html.parser')
    scrapped_data = []
    enquiry_blocks = soup.select(bs_config['ENQUIRY_BLOCK_SELECTOR'])
    print(f"{len(enquiry_blocks)} enquiry blocks for parsing.")
    for block in enquiry_blocks:
        data_entry = {}

        try:
            details_line_element = block.select_one(bs_config['DETAILS_LINE_SELECTOR'])
            if details_line_element:
                details_text = details_line_element.text.strip()
                parts = [p.strip() for p in details_text.split(' | ')]

                data_entry['DateTime'] = parts[0] if len(parts) > 0 else "N/A"
                data_entry['Ref_No'] = parts[1].replace("Ref No:", "").strip() if len(parts) > 1 else "N/A"
                data_entry['Location'] = parts[2] if len(parts) > 2 else "N/A"
                data_entry['Customer_Name'] = parts[3] if len(parts) > 3 else "N/A"
            else:
                data_entry['DateTime'] = data_entry['Ref_No'] = data_entry['Location'] = data_entry[
                    'Customer_Name'] = "N/A"
        except Exception as e:
            print("Failed to Parse Details: " + e)
        try:
            car_line_element = block.select_one(bs_config['CAR_LINE_SELECTOR'])
            data_entry['Car_Details'] = car_line_element.text.strip() if car_line_element else "N/A"
        except Exception:
            data_entry['Car_Details'] = "N/A"

        try:
            part_name_element = block.select_one(bs_config['PART_NAME_SELECTOR'])
            data_entry['Part_Name'] = part_name_element.text.strip() if part_name_element else "N/A"
        except Exception:
            data_entry['Part_Name'] = "N/A"

        try:
            part_condition_element = block.select_one(bs_config['PART_CONDITION_SELECTOR'])
            # Assuming the text is "Part Condition: Used"
            data_entry['Part_Condition'] = part_condition_element.text.replace("Part Condition:",
                                                                               "").strip() if part_condition_element else "N/A"
        except Exception:
            data_entry['Part_Condition'] = "N/A"

        data_entry['Phone_Number'] = "N/A"
        try:
            # Find the phone button element using the CSS selector
            phone_btn = block.select_one(bs_config['PHONE_BTN_SELECTOR'])
            if phone_btn and phone_btn.has_attr('onclick'):
                onclick_value = phone_btn['onclick']
                # print(onclick_value.split(",")[-3].split(":")[-1].rstrip("'"))

                number = onclick_value.split(",")[-3].split(":")[-1].rstrip("'")
                data_entry['Phone_Number'] = number
        except Exception as e:
            print(f"Warning: Failed to extract phone number. Error: {e}")
            pass

        try:
            whatsapp_element = block.select_one(bs_config['WHATSAPP_BTN_SELECTOR'])
            # print(whatsapp_element)
            if whatsapp_element and whatsapp_element.has_attr('onclick'):
                # print(whatsapp_element['onclick'])
                wa_number = whatsapp_element['onclick'].split(",")[-3].split("&&")[0].split("=")[-1]
                # print(wa_number)
                data_entry['WhatsApp_Number'] = wa_number
            else:
                data_entry['WhatsApp_Number'] = "N/A"

        except Exception as e:
            print("Error while extracting whatsapp: " + e)
            data_entry['WhatsApp_Number'] = "N/A"
        # print(data_entry)
        scrapped_data.append(data_entry)
    return scrapped_data


@app.route('/', methods=['GET'])
def greet():
    return "Hellow"


@app.route('/scrape', methods=['GET', 'POST'])
def scrape():
    # Define Configuration
    print("Starting")
    my_config = Config(
        login_url="https://www.partfinder.in/members/login",
        enquiries_url="https://www.partfinder.in/members/enquiries",
        username="09666448896",
        password="Surya@8896"
    )

    # STEP 1: Get the HTML source using Selenium
    html_source = get_page_info(my_config)
    IST_TZ = pytz.timezone("Asia/Kolkata")
    now = datetime.now(IST_TZ)
    timestamp_str = now.strftime("%Y-%m-%d %H-%M-%S")
    if html_source:
        # STEP 2: Extract data from the source using Beautiful Soup
        data = extract_data_from_html(html_source, BS_CONFIG)
        print(data)

        # STEP 3: Save the extracted data to CSV
        # OUTPUT_FILE = f'partfinder_enquiries {timestamp_str}.csv'

        # if data:
        #     print(f"\n8. Saving {len(data)} records to {OUTPUT_FILE}...")
        #
        #     # --- FINAL CSV FIELD NAMES ---
        #     fieldnames = [
        #         'DateTime', 'Ref_No', 'Location', 'Customer_Name',
        #         'Car_Details', 'Part_Condition', 'Part_Name',
        #         'Email_ID', 'Phone_Number', 'WhatsApp_Number'
        #     ]
        #
        #     with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        #         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        #         writer.writeheader()
        #         writer.writerows(data)
        #
        #     print(f"9. Successfully saved data to {OUTPUT_FILE}")
        # else:
        #     print("\n8. No data extracted to save.")
    return {
        "message": "Operation Complete",
        "data": data
    }


if __name__ == "__main__":
    app.run(debug=True)
