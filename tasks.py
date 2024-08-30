import os
import re
import time
import requests
import urllib.parse
from datetime import datetime, timedelta
from robocorp.tasks import task
from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files
from robocorp import workitems

# Global constants
SAVE_FOLDER = "output"

# Ensure the folder exists
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Download image function
def download_image(image_url: str) -> str:
    """Download an image and save it to the output folder."""
    decoded_url = urllib.parse.unquote(image_url)
    image_name = os.path.basename(decoded_url)
    image_path = os.path.join(SAVE_FOLDER, image_name)
    
    # File download request
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        with open(image_path, 'wb') as file:
            file.write(response.content)
        print(f"Image successfully downloaded: {image_path}")
    except requests.RequestException as e:
        print(f"Failed to download image: {e}")
        return ""
    
    return image_path
# function designed to process the whole transaction
def get_news(limit_date: str, phrase: str) -> list:
    """Scrape news articles and store them in an Excel file."""
    current_date = datetime.now()
    # Verifies if limit date is valid
    # Number based format
    # 0 | 1 would get current month, 2 would get previous and current
    # 3 would get data from 2 previous months and current month. 
    if limit_date in {"1", "0"}:
        limit_date = current_date
        print(f"Checking current month: {limit_date.strftime('%B %Y')}")
    elif limit_date == "2":
        limit_date = current_date - timedelta(days=current_date.day)
        print(f"Checking past month: {limit_date.strftime('%B %Y')}")
    elif limit_date == "3":
        first_day_of_current_month = current_date.replace(day=1)
        limit_date = first_day_of_current_month - timedelta(days=1)
        previous_month_before = limit_date.replace(day=1)
        print(f"Checking the month before the past month: {previous_month_before.strftime('%B %Y')}")
    else:
        raise ValueError("Invalid limit date. Please choose from 1-3.")
    # Prepare output file
    excel = Files()
    # Set browser configuration
    browser = Selenium(auto_close=True)
    browser.set_selenium_timeout(10)
    browser.set_download_directory(SAVE_FOLDER)
    browser.open_browser(f"https://www.latimes.com/search?q={phrase}", browser="edge")
    # articles to be stored
    articles = []
    # Scraping flag for data limitation
    stop_scraping = False
    # Money patter RegEx possible formats: $11.1 | $111,111.11 | 11 dollars | 11 USD
    money_pattern = r"\$\d+(?:,\d{3})*(?:\.\d{2})?|(?:\d+(?:,\d{3})*\.\d{2})?\s*(dollars|USD)"
    # News Scrapping
    while True:
        elements = browser.find_elements("//div[@class='promo-wrapper']")
        for element in elements:
            try:
                title = element.find_element("xpath", ".//div[@class='promo-title-container']").text
                description = element.find_element("xpath", ".//p[@class='promo-description']").text
                date_text = element.find_element("xpath", './/p[@class="promo-timestamp"]').text
                image_url = element.find_element("xpath", ".//img[@class='image']").get_attribute("src")
            except Exception as e:
                print(f"Error extracting element data: {e}")
                continue

            image_path = download_image(image_url)

            try:
                date = datetime.strptime(date_text, "%b. %d, %Y")
            except ValueError:
                try:
                    date = datetime.strptime(date_text, "%B %d, %Y")
                except ValueError:
                    print(f"Invalid date format: {date_text}")
                    continue

            matches = re.findall(money_pattern, description, re.IGNORECASE)
            # Limit date validation
            if date < limit_date:
                stop_scraping = True
                break

            has_money_text = bool(matches)
            # Add object to articles
            articles.append({
                "title": title,
                "description": description,
                "date": date.strftime('%m-%d-%Y'),
                "words in title": title.lower().count(phrase.lower()),
                "words in description": description.lower().count(phrase.lower()),
                "contains money related news": has_money_text,
                "image": image_path
            })
        # Validates Next botton available.
        next_buttons = browser.find_elements('//div[@Class="search-results-module-next-page"]')

        if stop_scraping or not next_buttons:
            break
        elif next_buttons:
            browser.click_element_when_visible(next_buttons[0])

    if articles:
        # Generates excel output file
        excel.create_workbook()
        headers = [
            "title", "description", "date", "words in title",
            "words in description", "contains money related news", "image"
        ]
        for col_index, header in enumerate(headers, start=1):
            excel.set_cell_value(1, col_index, header)

        for row_index, row_data in enumerate(articles, start=1):
            for col_index, cell_value in enumerate(headers, start=1):
                excel.set_cell_value(row_index + 1, col_index, row_data[cell_value])
        # Saves excel output file
        excel_path = os.path.join(SAVE_FOLDER, 'Output.xlsx')
        excel.save_workbook(excel_path)
        excel.close_workbook()
        print("Ending simple web scraping.")
        time.sleep(10)

    return articles

@task
def producer() -> None:
    for item in workitems.inputs:
        print("Testing my own item")
        print(item)
        try:
            articles = get_news(item.payload["limit_date"], item.payload["phrase"])
            for article in articles:
                print("********************************")
                print(article)
        except ValueError as e:
            print(f"Error: {e}")
