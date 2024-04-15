import json
import requests
import re
import datetime
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Global state for attack persistence
attack_states = {
    'roxcheck1': 0  
}

def setup_headless_chrome():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-data-dir=/tmp/chrome-user-data")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def fetch_json(url):
    response = requests.get(url)
    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {url}")
            return None
    else:
        print(f"Failed to fetch data from {url}, Status Code: {response.status_code}")
        return None

def is_ethereum_address(value):
    """Check if the given value is a valid Ethereum address."""
    return re.match(r'^0x[a-fA-F0-9]{40}$', value, re.IGNORECASE) is not None

def find_ethereum_addresses(data):
    """Recursively search for Ethereum addresses in JSON data."""
    if isinstance(data, dict):
        for value in data.values():
            yield from find_ethereum_addresses(value)
    elif isinstance(data, list):
        for item in data:
            yield from find_ethereum_addresses(item)
    elif isinstance(data, str) and is_ethereum_address(data):
        yield data.lower()

def fetch_json_data(url):
    """Fetch JSON from the URL and extract all Ethereum addresses."""
    data = fetch_json(url)
    if data:
        return set(find_ethereum_addresses(data))
    return set()

def scrape_webpage_for_ethereum_addresses(url):
    driver = setup_headless_chrome()
    try:
        driver.get(url)
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        webpage_content = driver.page_source
        raw_addresses = re.findall(r'0x[a-fA-F0-9]{40}', webpage_content, re.IGNORECASE)
        valid_addresses = {addr.lower() for addr in raw_addresses if is_ethereum_address(addr)}
        return valid_addresses
    finally:
        driver.quit()

def compare_addresses(initial_data, current_data):
    added = current_data - initial_data
    removed = initial_data - current_data
    return added, removed

def alert(url, added, removed):
    if added or removed:
        alert_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "url": url,
            "added_values": list(added),
            "removed_values": list(removed),
            "notes_for_remediation": "Review the changes and apply necessary security measures or rollbacks."
        }
        filename = f"alert_{datetime.datetime.now().isoformat()}.json"
        with open(filename, "w") as file:
            json.dump(alert_data, file, indent=4)
        print(f"Alert saved to {filename}")
        print(json.dumps(alert_data, indent=4))

def simulate_attack(iteration, url, data):
    if not data:
        print(f"No addresses found in {url}, skipping attack simulation.")
        return

    if url == 'https://www.zetachain.com/docs/reference/contracts/':
        if (iteration == 3 or iteration == 4) and 'roxcheck1' not in data:
            random_address = random.choice(list(data))
            data.remove(random_address)
            data.add("roxcheck1")
            if iteration == 3:
                attack_states['roxcheck1'] = 2 

        if iteration == 4:
            data.add("roxcheck2")

    elif url == 'https://raw.githubusercontent.com/zeta-chain/protocol-contracts/main/data/addresses.mainnet.json' and iteration == 5:
        random_address = random.choice(list(data))
        data.remove(random_address)
        data.add("roxcheck3")


def main():
    urls = [
        'https://raw.githubusercontent.com/zeta-chain/protocol-contracts/main/data/addresses.mainnet.json',
        'https://raw.githubusercontent.com/zeta-chain/protocol-contracts/main/data/addresses.testnet.json',
        'https://raw.githubusercontent.com/zeta-chain/app-contracts/main/packages/zevm-app-contracts/data/addresses.json',
        'https://raw.githubusercontent.com/zeta-chain/app-contracts/main/packages/zeta-app-contracts/data/addresses.json',
        'https://www.zetachain.com/docs/reference/contracts/'
    ]
    initial_data = {url: fetch_json_data(url) for url in urls[:-1]}
    initial_data[urls[-1]] = scrape_webpage_for_ethereum_addresses(urls[-1])

    for iteration in range(1, 7):
        print(f"Iteration {iteration} starting...")
        for url in urls:
            current_data = scrape_webpage_for_ethereum_addresses(url) if url.endswith('/') else fetch_json_data(url)
            simulate_attack(iteration, url, current_data)
            added, removed = compare_addresses(initial_data[url], current_data)
            alert(url, added, removed)

if __name__ == "__main__":
    main()
