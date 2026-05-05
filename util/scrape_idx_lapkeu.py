import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By



def search_company_list(ticker):
    url = 'https://idx.co.id/perusahaan-tercatat/laporan-keuangan-dan-tahunan/'
    years = ['2022','2023','2024','2025']
    quarters = ['tw1','tw2','tw3','audit']
    for year in years:
        for quarter in quarters:
            print(f"Processing {year}-{quarter}")
            driver = webdriver.Chrome()
            driver.minimize_window()
            driver.get(url)
            driver.implicitly_wait(5)
            time.sleep(2)
            input_field = driver.find_element(By.XPATH, '//input[contains(@placeholder, "Search Company Code")]')
            input_field.send_keys(ticker)
            time.sleep(3)
            input_field.send_keys(Keys.ENTER)

            
            time.sleep(4)
            year_btn = driver.find_element(By.XPATH,f'//input[contains(@value, "{year}")]')
            year_btn.click()
            time.sleep(0.5)
            quarter_btn = driver.find_element(By.XPATH,f'//input[contains(@value, "{quarter}")]')
            quarter_btn.click()
            time.sleep(1)
            terapkan_btn = driver.find_element(By.XPATH, '//button[contains(text(), "Terapkan")]')
            terapkan_btn.click()
            time.sleep(2)
            try:
                download_btn = driver.find_element(By.XPATH,"//td[contains(text(), 'FinancialStatement') and contains(text(), '.pdf')]/following-sibling::td")
                download_btn.click()
            except:pass
            time.sleep(2)
            driver.close()    
    
search_company_list("BREN")

for ticker in ["BMRI","BBRI","BBNI"]:
    search_company_list(ticker)
